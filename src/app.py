import dearpygui.dearpygui as dpg
from numpy.core.fromnumeric import size
from tools import importMHD, array2image, loadLabels, getLabelStats
import numpy as np
from fluoroscopy import fluoroscopy
import os

class MainApp():
    def __init__(self):
        self.mainWinWidth = 630
        self.mainWinHeight = 1300

        vp = dpg.create_viewport(title='GGEMS C-Arm', width=self.mainWinWidth, height=self.mainWinHeight, 
                                 clear_color=(39, 44, 53, 255), x_pos=0, y_pos=0) # create viewport takes in config options too!
        dpg.setup_dearpygui(viewport=vp)
        dpg.show_viewport(vp)

        with dpg.file_dialog(directory_selector=False, show=False, callback=self.open_mhd, id='file_dialog_id'):
            dpg.add_file_extension(".mhd", color=(255, 255, 0, 255))
        self.phantomFilePath = ''
        self.flagPhantomLoaded = False

        self.colorTitle = (15, 157, 255, 255)  # Blue
        self.colorInfo = (255, 255, 0, 255)  # Yellow
        self.colorSource = (255, 255, 0, 255)  # Yellow
        self.colorPanel = (0, 255, 0, 255) # Green
        self.colorLineOfSight = (174, 214, 241, 255) # light blue
        self.colorPatient = (253, 237, 236, 255) # light pink

        # Size of the c-arm draw zone
        self.carmDrawWidth = 200
        self.carmDrawHeight = 200

        # Size of the ct draw zone
        self.ctDrawWidth = 200
        self.ctDrawHeight = 200

        # CT viewer
        self.ctTexParams = {
            'pMin': 0,
            'pMax': 0,
            'nbSlices': 0,
        }

        # Labels
        self.labels = {}

        # Fluorscopy viewer
        # Flag that determine if the CT have to be reconvert into mumap
        self.fluoRequestMuMap = True
        self.fluoEngine = fluoroscopy()
        self.fluoPanelNx = 256
        self.fluoPanelNy = 256
        self.fluoPanelSx = 2.0
        self.fluoPanelSy = 2.0
        self.fluoEnergy = 80.0
        self.fluoFlagFirstViewing = True

        # Change to draw frame
        self.panelFrame = np.matrix([[self.carmDrawWidth//2],
                                     [self.carmDrawHeight//2],
                                     [0]], 'float32')

        ### Config C-arm (ref uses image frame)
        #
        # Source
        self.carmDistISOSource = 600
        self.carmOrgPosSource = np.matrix([[0],
                                           [self.carmDistISOSource],
                                           [0]], 'float32')
        self.carmPosSource = np.copy(self.carmOrgPosSource)
        
        # Flat panel
        self.carmDistISOPanel = dp = 400
        self.flatPanelHalfSize = hs = 200 # flatPanelHalfSize
        self.carmOrgPosPointsPanel = np.matrix([[-hs,  hs,  hs, -hs],
                                                [-dp, -dp, -dp, -dp],
                                                [ hs,  hs, -hs, -hs]], 'float32')
        self.carmPosPointsPanel = np.copy(self.carmOrgPosPointsPanel)

        # Translation
        self.carmTranslation = np.matrix([[0],
                                          [0],
                                          [0]], 'float32')
        # Rotation around Z (LAO-RAO)
        self.carmRotZ = np.matrix([[1, 0, 0],
                                   [0, 1, 0],
                                   [0, 0, 1]], 'float32')

        # Rotation around X (CRA-CAU)
        self.carmRotX = np.matrix([[1, 0, 0],
                                   [0, 1, 0],
                                   [0, 0, 1]], 'float32')

        # Projection on ZY plane
        scaling = 0.15
        self.carmProjZY = np.matrix([[0,       0, scaling], 
                                     [0, scaling,       0], 
                                     [0,       0,       0]], 'float32')
        # Projection on XZ
        self.carmProjXZ = np.matrix([[0,       0,  scaling], 
                                     [scaling, 0,        0], 
                                     [0,       0,        0]], 'float32')

        # Patient
        self.patientThoraxSize = (600*scaling, 200*scaling, 300*scaling)  # mm (length, thickness, width)
        self.patientHead = (100*scaling)  # radius in mm
        self.patientArm = (100*scaling, 400*scaling, 100*scaling)  # offset, length, thickness in mm

    def open_mhd(self, sender, app_data):

        if app_data['file_name'] != '.mhd':
            self.phantomFilePath = app_data['file_path_name']
            self.arrayRaw, self.dictHeader = importMHD(self.phantomFilePath)
            nx, ny, nz = self.dictHeader['shape']
            sx, sy, sz = self.dictHeader['spacing']
            filename = app_data['file_name']
            txt = '%s   %ix%ix%i pix   %4.2fx%4.2fx%4.2f mm' % (filename, nx, ny, nz, sx, sy, sz)
            dpg.set_value('txt_info_image_file', txt)
            
            # Convert into texture
            dpg.set_value('txtInfo', 'Loading...')
            dpg.configure_item('infoWindow', show=True)
            with dpg.texture_registry():
                for iSlice in range(nz):
                    image = array2image(self.arrayRaw[iSlice])
                    dpg.add_static_texture(nx, ny, image, id='CT%i' % iSlice)
            dpg.configure_item('infoWindow', show=False)

            # Manage ratio and centering
            ratio = nx / ny
            if ratio > 1:
                newWidth = self.ctDrawWidth
                newHeight = self.ctDrawWidth / ratio
                paddingH = (self.ctDrawHeight-newHeight) / 2.0
                paddingW = 0
            elif ratio < 1:
                newWidth = self.ctDrawHeight * ratio
                newHeight = self.ctDrawHeight
                paddingH = 0
                paddingW = (self.ctDrawWidth-newWidth) / 2.0
            else:
                newWidth = self.ctDrawWidth
                newHeight = self.ctDrawHeight
                paddingH = 0
                paddingW = 0

            self.ctTexParams['pMin'] = (paddingW+1, paddingH+1)
            self.ctTexParams['pMax'] = (paddingW+newWidth-1, paddingH+newHeight-1)

            self.ctTexParams['nbSlices'] = nz-1

            # Configure the slicer and draw the first image
            dpg.configure_item('slicerCT', default_value=nz//2, max_value=nz-1)
            dpg.draw_image(parent='render_ct', texture_id='CT%i' % (nz//2), 
                           pmin=self.ctTexParams['pMin'], 
                           pmax=self.ctTexParams['pMax'], 
                           uv_min=(0, 0), uv_max=(1, 1),
                           id='imageCT')

            #### Check for labels
            labelPathName = os.path.dirname(self.phantomFilePath)
            self.labelFileName = os.path.join(labelPathName, 'Segmentation-label.mhd')
            labelTableFileName = os.path.join(labelPathName, 'Segmentation-label_ColorTable.txt')

            if os.path.isfile(self.labelFileName) and os.path.isfile(labelTableFileName):
                self.rawLabel, self.dictLabel = importMHD(self.labelFileName)

                # Convert into texture
                dpg.set_value('txtInfo', 'Loading...')
                dpg.configure_item('infoWindow', show=True)
                with dpg.texture_registry():
                    for iSlice in range(nz):
                        image = array2image(self.rawLabel[iSlice])
                        dpg.add_static_texture(nx, ny, image, id='Label%i' % iSlice)
                dpg.configure_item('infoWindow', show=False)

                # Draw
                dpg.draw_image(parent='render_labels', texture_id='Label%i' % (nz//2), 
                                pmin=self.ctTexParams['pMin'], 
                                pmax=self.ctTexParams['pMax'], 
                                uv_min=(0, 0), uv_max=(1, 1),
                                id='imageLabel')

                # Load labels
                self.labels = loadLabels(labelTableFileName)

                txt = ''
                for key in self.labels.keys():
                    if key != 'Background':
                        txt += (key + ' ')
                        
                dpg.set_value('txt_info_label_file', txt)

            dpg.configure_item('groupStep2', show=True)
            
        else:
            pass # TODO

    def callBackSlicerCT(self, sender, app_data):
        dpg.delete_item('imageCT')
        dpg.draw_image(parent='render_ct', texture_id='CT%i' % app_data, 
                       pmin=self.ctTexParams['pMin'], 
                       pmax=self.ctTexParams['pMax'], 
                       uv_min=(0, 0), uv_max=(1, 1),
                       id='imageCT')

        dpg.delete_item('imageLabel')
        dpg.draw_image(parent='render_labels', texture_id='Label%i' % app_data, 
                       pmin=self.ctTexParams['pMin'], 
                       pmax=self.ctTexParams['pMax'], 
                       uv_min=(0, 0), uv_max=(1, 1),
                       id='imageLabel')

    def callBackLAORAO(self, sender, app_data):
        ang = np.pi*app_data / 180.0
        ca = np.cos(ang)
        sa = np.sin(ang)
        self.carmRotZ[0] = [ca, -sa, 0]
        self.carmRotZ[1] = [sa,  ca, 0]
        self.carmRotZ[2] = [ 0,   0, 1]
        self.updateCarmDraw()

    def callBackCAUCRA(self, sender, app_data):
        ang = np.pi*app_data / 180.0
        ca = np.cos(ang)
        sa = np.sin(ang)
        self.carmRotX[0] = [1,  0,   0]
        self.carmRotX[1] = [0, ca, -sa]
        self.carmRotX[2] = [0, sa,  ca]
        self.updateCarmDraw()

    def callBackTransX(self, sender, app_data):
        self.carmTranslation[0][0] = app_data
        self.updateCarmDraw()
    
    def callBackTransY(self, sender, app_data):
        self.carmTranslation[1][0] = app_data
        self.updateCarmDraw()

    def callBackTransZ(self, sender, app_data):
        self.carmTranslation[2][0] = app_data
        self.updateCarmDraw()

    def callBackResetCarm(self, sender, app_data):
        ang = 0
        ang = np.pi*ang / 180.0

        ca = np.cos(ang)
        sa = np.sin(ang)
        self.carmRotX[0] = [1,  0,   0]
        self.carmRotX[1] = [0, ca, -sa]
        self.carmRotX[2] = [0, sa,  ca]

        ca = np.cos(ang)
        sa = np.sin(ang)
        self.carmRotZ[0] = [ca, -sa, 0]
        self.carmRotZ[1] = [sa,  ca, 0]
        self.carmRotZ[2] = [ 0,   0, 1]

        self.carmTranslation[0][0] = 0
        self.carmTranslation[1][0] = 0
        self.carmTranslation[2][0] = 0
        self.fluoEnergy = 80.0
        self.fluoRequestMuMap = True

        dpg.configure_item('sliderLAORAO', default_value=0)
        dpg.configure_item('sliderCAUCRA', default_value=0)
        dpg.configure_item('sliderTX', default_value=0)
        dpg.configure_item('sliderTY', default_value=0)
        dpg.configure_item('sliderTZ', default_value=0)
        dpg.configure_item('inputVoltage', default_value=80.0)

        self.updateCarmDraw()
        
    def callBackVoltage(self, sender, app_data):
        self.fluoEnergy = app_data
        # If the energy change the CT have to convert into mumap accordingly
        self.fluoRequestMuMap = True

    def callBackGetDDR(self):
        self.fluoEngine.setPose(self.carmRotX, self.carmRotZ, self.carmTranslation)
        self.fluoEngine.setCamera(self.fluoPanelNx, self.fluoPanelNy, 
                                    self.fluoPanelSx, self.fluoPanelSy, self.carmDistISOPanel)

        if self.fluoRequestMuMap:
            #                            kVp -> peak MeV
            self.fluoEngine.setSource(0.001*self.fluoEnergy/2.0, self.carmDistISOSource)
            self.fluoEngine.setImage(self.arrayRaw, self.dictHeader)
            self.fluoEngine.computeMuMap()
            self.fluoRequestMuMap = False

        imageDDR = self.fluoEngine.getProjection()
        image = array2image(imageDDR)

        # Manage ratio and centering
        ratio = self.fluoPanelNx / self.fluoPanelNy
        if ratio > 1:
            newWidth = self.carmDrawWidth
            newHeight = self.carmDrawWidth / ratio
            paddingH = (self.carmDrawHeight-newHeight) / 2.0
            paddingW = 0
        elif ratio < 1:
            newWidth = self.carmDrawHeight * ratio
            newHeight = self.carmDrawHeight
            paddingH = 0
            paddingW = (self.carmDrawWidth-newWidth) / 2.0
        else:
            newWidth = self.carmDrawWidth
            newHeight = self.carmDrawHeight
            paddingH = 0
            paddingW = 0

        if self.fluoFlagFirstViewing:
            with dpg.texture_registry():
                dpg.add_dynamic_texture(self.fluoPanelNx, self.fluoPanelNy, image, id='texture_ddr')

            dpg.draw_image(parent='render_carm_ddr', texture_id='texture_ddr', 
                            pmin=(paddingW+1, paddingH+1), 
                            pmax=(paddingW+newWidth-1, paddingH+newHeight-1), 
                            uv_min=(0, 0), uv_max=(1, 1),
                            id='imageFluo')

            self.fluoFlagFirstViewing = False
        else:
            dpg.set_value('texture_ddr', image)

        dpg.configure_item('groupStep3', show=True) 

    def callBackRunGGEMS(self):
        from sys import exit
        try:
            import spekpy as sp
        except:
            print('Impossible to load spekpy module')
            exit()

        try:
            from ggems import GGEMSVerbosity, GGEMSOpenCLManager, GGEMSMaterialsDatabaseManager, GGEMSCTSystem, GGEMSRangeCutsManager
            from ggems import GGEMSVoxelizedPhantom, GGEMSDosimetryCalculator, GGEMSProcessesManager, GGEMSXRaySource, GGEMS
        except:
            print('Impossible to load GGEMS module')
            exit()

        # 1. Build spectrum
        s = sp.Spek(kvp=self.fluoEnergy, th=8) # Create a spectrum U, theta
        s.filter('Al', 2) # Filter the spectrum 2 mm
        k, f = s.get_spectrum() # Get the spectrum
        f /= f.sum()  # normalize
        k /= 1000.0   # convert keV -> MeV

        file = open('spectrum.temp', 'w')
        for i in range(len(k)):
            file.write('%0.10f %0.10f\n' % (k[i], f[i]))
        file.close()

        # 2. Get data
        device_id = dpg.get_value('inputGPUID')
        nb_particles = np.int64(dpg.get_value('inputNbParticles')) * np.int64(1e06)
        flagTLE = dpg.get_value('checkTLE')

        angZ = dpg.get_value('sliderLAORAO') - 90  # change org
        angX = dpg.get_value('sliderCAUCRA')
        tx = float(-self.carmTranslation[0][0])           # Instead moving the c-arm we move the phantom
        ty = float(-self.carmTranslation[1][0]) 
        tz = float(-self.carmTranslation[2][0])
        sx, sy, sz = self.dictHeader['spacing']
        angAperture = dpg.get_value('inputAperture')

        print('#### Info ####')
        print('id', device_id, 'nbphot', nb_particles, 'flagTLE', flagTLE)
        print('ang', angX, angZ, 'T', tx, ty, tz)
        print('Scaling', sx, sy, sz)
        print('Aperture', angAperture)

        # 3. GGEMS
        dpg.set_value('txtInfo', 'Running...')
        dpg.configure_item('infoWindow', show=True)

        # Verbo
        GGEMSVerbosity(0)

        # Device
        opencl_manager = GGEMSOpenCLManager()
        opencl_manager.set_device_index(device_id)

        # Material
        materials_database_manager = GGEMSMaterialsDatabaseManager()
        materials_database_manager.set_materials('src/materials.txt')

        # Loading phantom
        tx, ty, tx = self.carmTranslation
        phantom0 = GGEMSVoxelizedPhantom('phantom')
        phantom0.set_phantom(self.phantomFilePath, 'src/HU2mat.txt')
        phantom0.set_rotation(0.0, 0.0, 0.0, 'deg')
        phantom0.set_position(tx, ty, tz, 'mm')

        # ------------------------------------------------------------------------------
        # STEP 4: Dosimetry
        dosimetry = GGEMSDosimetryCalculator()
        dosimetry.attach_to_navigator('phantom')
        dosimetry.set_output_basename('output/dosimetry')
        dosimetry.set_dosel_size(sx, sy, sz, 'mm')
        dosimetry.water_reference(False)
        dosimetry.minimum_density(0.1, 'g/cm3')
        dosimetry.set_tle(flagTLE)

        dosimetry.uncertainty(True)
        dosimetry.photon_tracking(False)
        dosimetry.edep(False)
        dosimetry.hit(False)
        dosimetry.edep_squared(False)

        # Detector
        ct_detector = GGEMSCTSystem('C-arm')
        ct_detector.set_ct_type('flat')
        ct_detector.set_number_of_modules(1, 1)
        ct_detector.set_number_of_detection_elements(self.fluoPanelNx, self.fluoPanelNy, 1)
        ct_detector.set_size_of_detection_elements(self.fluoPanelSx, self.fluoPanelSy, 1, 'mm')
        ct_detector.set_material('GSO')
        ct_detector.set_source_detector_distance(self.carmDistISOSource+self.carmDistISOPanel, 'mm')
        ct_detector.set_source_isocenter_distance(self.carmDistISOSource, 'mm')
        ct_detector.set_rotation(angX, 0.0, angZ, 'deg')
        ct_detector.set_threshold(10.0, 'keV')
        ct_detector.save('output/projection.mhd')

        # ------------------------------------------------------------------------------
        # STEP 5: Physics
        processes_manager = GGEMSProcessesManager()
        processes_manager.add_process('Compton', 'gamma', 'all')
        processes_manager.add_process('Photoelectric', 'gamma', 'all')
        processes_manager.add_process('Rayleigh', 'gamma', 'all')

        # Optional options, the following are by default
        processes_manager.set_cross_section_table_number_of_bins(220)
        processes_manager.set_cross_section_table_energy_min(1.0, 'keV')
        processes_manager.set_cross_section_table_energy_max(1.0, 'MeV')

        # ------------------------------------------------------------------------------
        # STEP 6: Cuts, by default but are 1 um
        range_cuts_manager = GGEMSRangeCutsManager()
        range_cuts_manager.set_cut('gamma', 0.1, 'mm', 'all')

        # ------------------------------------------------------------------------------
        # STEP 7: Source
        point_source = GGEMSXRaySource('xsource')
        point_source.set_source_particle_type('gamma')
        point_source.set_number_of_particles(nb_particles)   ### 
        point_source.set_position(-self.carmDistISOSource, 0.0, 0.0, 'mm')
        point_source.set_rotation(angX, 0.0, angZ, 'deg')
        point_source.set_beam_aperture(angAperture, 'deg')
        point_source.set_focal_spot_size(0.0, 0.0, 0.0, 'mm')
        point_source.set_polyenergy('spectrum.temp')

        # ------------------------------------------------------------------------------
        # STEP 8: GGEMS simulation
        ggems = GGEMS()
        ggems.opencl_verbose(False)
        ggems.material_database_verbose(False)
        ggems.navigator_verbose(False)
        ggems.source_verbose(False)
        ggems.memory_verbose(False)
        ggems.process_verbose(False)
        ggems.range_cuts_verbose(False)
        ggems.random_verbose(False)
        ggems.profiling_verbose(False)
        ggems.tracking_verbose(False, 0)

        # Initializing the GGEMS simulation
        seed = 123456789
        ggems.initialize(seed)

        # Start GGEMS simulation
        ggems.run()
        
        # ------------------------------------------------------------------------------
        # STEP 9: Exit code
        dosimetry.delete()
        ggems.delete()
        opencl_manager.clean()

        dpg.configure_item('infoWindow', show=False)

        # Show result
        self.showResult()
                
    def updateCarmConfiguration(self):
        # Update source position
        self.carmPosSource = self.carmRotX * self.carmOrgPosSource
        self.carmPosSource = self.carmRotZ * self.carmPosSource
        self.carmPosSource += self.carmTranslation

        # Update panel position
        self.carmPosPointsPanel = self.carmRotX * self.carmOrgPosPointsPanel
        self.carmPosPointsPanel = self.carmRotZ * self.carmPosPointsPanel
        self.carmPosPointsPanel += self.carmTranslation

    # Create the first items
    def firstCarmDraw(self):
        ## Left view #################
        #
        d = 10

        
        # Isocenter
        cx = self.panelFrame[0][0]
        cy = self.panelFrame[1][0]
        dpg.draw_line(parent='render_carm_left', p1=(cx, cy), p2=(cx+d, cy), color=(0, 0, 255, 255))
        dpg.draw_line(parent='render_carm_left', p1=(cx, cy), p2=(cx, cy+d), color=(0, 255, 0, 255))
                                                                              
        # Source
        dpg.draw_triangle(parent='render_carm_left', p1=(0, 0), p2=(0, 0), p3=(0, 0), color=self.colorSource, id='l_src')

        # Flat panel
        dpg.draw_polygon(parent='render_carm_left', points=[(0, 0), (0, 0)], color=self.colorPanel, id='l_panel')

        # Line of sight
        dpg.draw_line(parent='render_carm_left', p1=(0, 0), p2=(0, 0), color=self.colorLineOfSight, id='l_los_1')
        dpg.draw_line(parent='render_carm_left', p1=(0, 0), p2=(0, 0), color=self.colorLineOfSight, id='l_los_2')
        dpg.draw_line(parent='render_carm_left', p1=(0, 0), p2=(0, 0), color=self.colorLineOfSight, id='l_los_3')
        dpg.draw_line(parent='render_carm_left', p1=(0, 0), p2=(0, 0), color=self.colorLineOfSight, id='l_los_4')

        # Patient
        hLength = self.patientThoraxSize[0] // 2
        hThick = self.patientThoraxSize[1] // 2
        dpg.draw_rectangle(parent='render_carm_left', pmin=(self.panelFrame[0]-hLength, self.panelFrame[1]-hThick), 
                           pmax=(self.panelFrame[0]+hLength, self.panelFrame[1]+hThick), rounding=2, color=self.colorPatient)

        hArmLength = self.patientArm[1] // 2
        offset = self.patientArm[0] // 2
        hArmThick = self.patientArm[2] // 2
        dpg.draw_rectangle(parent='render_carm_left', pmin=(self.panelFrame[0]-hArmLength+offset, self.panelFrame[1]-hThick+hArmThick), 
                           pmax=(self.panelFrame[0]+hArmLength+offset, self.panelFrame[1]+hThick-hArmThick), rounding=2, color=self.colorPatient)

        dpg.draw_circle(parent='render_carm_left', center=(hLength+self.patientHead+self.panelFrame[0], 
                                                           self.panelFrame[1]), 
                                                           radius=self.patientHead, color=self.colorPatient)
        

        ## Top view #################
        #

        
        # Isocenter
        cx = self.panelFrame[0][0]
        cy = self.panelFrame[1][0]
        dpg.draw_line(parent='render_carm_top', p1=(cx, cy), p2=(cx+d, cy), color=(0, 0, 255, 255))
        dpg.draw_line(parent='render_carm_top', p1=(cx, cy), p2=(cx, cy+d), color=(255, 0, 0, 255))
                                                                              
        # Source
        dpg.draw_triangle(parent='render_carm_top', p1=(0, 0), p2=(0, 0), p3=(0, 0), color=self.colorSource, id='t_src')

        # Flat panel
        dpg.draw_polygon(parent='render_carm_top', points=[(0, 0), (0, 0)], color=self.colorPanel, id='t_panel')

        # Line of sight
        dpg.draw_line(parent='render_carm_top', p1=(0, 0), p2=(0, 0), color=self.colorLineOfSight, id='t_los_1')
        dpg.draw_line(parent='render_carm_top', p1=(0, 0), p2=(0, 0), color=self.colorLineOfSight, id='t_los_2')
        dpg.draw_line(parent='render_carm_top', p1=(0, 0), p2=(0, 0), color=self.colorLineOfSight, id='t_los_3')
        dpg.draw_line(parent='render_carm_top', p1=(0, 0), p2=(0, 0), color=self.colorLineOfSight, id='t_los_4')

        # Patient
        hLength = self.patientThoraxSize[0] // 2
        hThick = self.patientThoraxSize[1] // 2
        hWidth = self.patientThoraxSize[2] // 2
        dpg.draw_rectangle(parent='render_carm_top', pmin=(self.panelFrame[0]-hLength, self.panelFrame[1]-hWidth), 
                           pmax=(self.panelFrame[0]+hLength, self.panelFrame[1]+hWidth), rounding=2, color=self.colorPatient)

        hArmLength = self.patientArm[1] // 2
        offset = self.patientArm[0] // 2
        ArmThick = self.patientArm[2]
        dpg.draw_rectangle(parent='render_carm_top', 
                           pmin=(self.panelFrame[0]-hArmLength+offset, self.panelFrame[1]-hWidth-ArmThick), 
                           pmax=(self.panelFrame[0]+hArmLength+offset, self.panelFrame[1]-hWidth), rounding=2, color=self.colorPatient)
        
        dpg.draw_rectangle(parent='render_carm_top', 
                           pmin=(self.panelFrame[0]-hArmLength+offset, self.panelFrame[1]+hWidth), 
                           pmax=(self.panelFrame[0]+hArmLength+offset, self.panelFrame[1]+hWidth+ArmThick), rounding=2, color=self.colorPatient)

        dpg.draw_circle(parent='render_carm_top', center=(hLength+self.patientHead+self.panelFrame[0], 
                                                           self.panelFrame[1]), 
                                                           radius=self.patientHead, color=self.colorPatient)

        ## DDR view #################
        #
  
    def updateCarmDraw(self):
        # Compute new conf
        self.updateCarmConfiguration()

        d = 2.5

        ## Left view ##################@
        #
                                                                            
        # Source
        pSource = (self.carmProjZY * self.carmPosSource) + self.panelFrame
        px = pSource[0][0]
        py = pSource[1][0]
        
        s1 = (px-d, py-d)
        s2 = (px+d, py-d)
        s3 = (px,   py+d)

        dpg.configure_item('l_src', p1=s1, p2=s2, p3=s3)

        # Panel
        pPanel = (self.carmProjZY * self.carmPosPointsPanel) + self.panelFrame
        pPanel = pPanel.A
        p1 = (pPanel[0][0], pPanel[1][0])
        p2 = (pPanel[0][1], pPanel[1][1])
        p3 = (pPanel[0][2], pPanel[1][2])
        p4 = (pPanel[0][3], pPanel[1][3])

        dpg.configure_item('l_panel', points=[p1, p2, p3, p4, p1])

        # Line of sight
        dpg.configure_item('l_los_1', p1=(px, py), p2=p1)
        dpg.configure_item('l_los_2', p1=(px, py), p2=p2)
        dpg.configure_item('l_los_3', p1=(px, py), p2=p3)
        dpg.configure_item('l_los_4', p1=(px, py), p2=p4)

        ## Top view ##################@
        #
                                                                              
        # Source
        pSource = (self.carmProjXZ * self.carmPosSource) + self.panelFrame
        px = pSource[0][0]
        py = pSource[1][0] 
        
        s1 = (px-d, py-d)
        s2 = (px+d, py-d)
        s3 = (px,   py+d)

        dpg.configure_item('t_src', p1=s1, p2=s2, p3=s3)

        # Panel
        pPanel = (self.carmProjXZ * self.carmPosPointsPanel) + self.panelFrame
        pPanel = pPanel.A
        p1 = (pPanel[0][0], pPanel[1][0])
        p2 = (pPanel[0][1], pPanel[1][1])
        p3 = (pPanel[0][2], pPanel[1][2])
        p4 = (pPanel[0][3], pPanel[1][3])

        dpg.configure_item('t_panel', points=[p1, p2, p3, p4, p1])

        # Line of sight
        dpg.configure_item('t_los_1', p1=(px, py), p2=p1)
        dpg.configure_item('t_los_2', p1=(px, py), p2=p2)
        dpg.configure_item('t_los_3', p1=(px, py), p2=p3)
        dpg.configure_item('t_los_4', p1=(px, py), p2=p4)

    def showResult(self):
        import os
        if os.path.isfile('output/dosimetry_dose.mhd') and os.path.isfile('output/dosimetry_uncertainty.mhd') and os.path.isfile('output/projection.mhd'):
            # Dose map
            rawDose, dictHeaderDose = importMHD('output/dosimetry_dose.mhd')
            
            nx, ny, nz = dictHeaderDose['shape']
            
            # Sum dose slice
            sliceDose = rawDose.sum(axis=0)

            # Convert into texture
            with dpg.texture_registry():
                image = array2image(sliceDose)
                dpg.add_static_texture(nx, ny, image, id='tex_dose')
            
            # Manage ratio and centering
            ratio = nx / ny
            if ratio > 1:
                newWidth = self.ctDrawWidth
                newHeight = self.ctDrawWidth / ratio
                paddingH = (self.ctDrawHeight-newHeight) / 2.0
                paddingW = 0
            elif ratio < 1:
                newWidth = self.ctDrawHeight * ratio
                newHeight = self.ctDrawHeight
                paddingH = 0
                paddingW = (self.ctDrawWidth-newWidth) / 2.0
            else:
                newWidth = self.ctDrawWidth
                newHeight = self.ctDrawHeight
                paddingH = 0
                paddingW = 0

            pMin = (paddingW+1, paddingH+1)
            pMax = (paddingW+newWidth-1, paddingH+newHeight-1)

            dpg.draw_image(parent='render_dose', texture_id='tex_dose', 
                           pmin=pMin, 
                           pmax=pMax, 
                           uv_min=(0, 0), uv_max=(1, 1))

            # Projection
            rawProj, dictHeaderProj = importMHD('output/projection.mhd')
            rawProj = rawProj[0]

            # Rotate and mirror for display
            rawProj = np.rot90(rawProj)
            rawProj = np.flipud(rawProj)

            # Enhance
            rawProj = np.log(rawProj+1)
            
            nx, ny, nz = dictHeaderProj['shape']

            # Convert into texture
            with dpg.texture_registry():
                image = array2image(rawProj)
                dpg.add_static_texture(nx, ny, image, id='tex_proj')
            
            # Manage ratio and centering
            ratio = nx / ny
            if ratio > 1:
                newWidth = self.ctDrawWidth
                newHeight = self.ctDrawWidth / ratio
                paddingH = (self.ctDrawHeight-newHeight) / 2.0
                paddingW = 0
            elif ratio < 1:
                newWidth = self.ctDrawHeight * ratio
                newHeight = self.ctDrawHeight
                paddingH = 0
                paddingW = (self.ctDrawWidth-newWidth) / 2.0
            else:
                newWidth = self.ctDrawWidth
                newHeight = self.ctDrawHeight
                paddingH = 0
                paddingW = 0

            pMin = (paddingW+1, paddingH+1)
            pMax = (paddingW+newWidth-1, paddingH+newHeight-1)

            dpg.draw_image(parent='render_proj', texture_id='tex_proj', 
                           pmin=pMin, 
                           pmax=pMax, 
                           uv_min=(0, 0), uv_max=(1, 1))

            ### Stats in table
            rawUnc, dictHeaderUnc = importMHD('output/dosimetry_uncertainty.mhd')
            print(rawUnc.min(), rawUnc.max(), rawUnc.mean(), rawUnc.dtype)

            if self.labels.keys() != 0:
                for key, val in self.labels.items():
                    if key=='Background': continue
                    dpg.add_text(key, parent='tableResults')
                    dpg.add_table_next_column(parent='tableResults')
                    # Dose
                    valMean, valSTD = getLabelStats(rawDose, val, self.rawLabel)
                    txt = '%0.3e +- %0.3e' % (valMean, valSTD)
                    dpg.add_text(txt, parent='tableResults')
                    dpg.add_table_next_column(parent='tableResults')
                    # Uncertainty
                    valMean, valSTD = getLabelStats(rawUnc, val, self.rawLabel)
                    txt = '%0.1f +- %0.1f %%' % (100*valMean, 100*valSTD)
                    dpg.add_text(txt, parent='tableResults')
                    dpg.add_table_next_column(parent='tableResults')
                   

    def show(self):
        with dpg.window(label='Main Window', width=self.mainWinWidth, height=self.mainWinHeight, pos=(0, 0), no_background=True,
                        no_move=True, no_resize=True, no_collapse=True, no_close=True, no_title_bar=True):
            
            ####################################################################
            dpg.add_text('Step 1', color=self.colorTitle)
            
            dpg.add_text('Select a patient file:')
            dpg.add_same_line(spacing=10)
            dpg.add_button(label='Open...', callback=lambda: dpg.show_item('file_dialog_id'))
            dpg.add_text('No file', id='txt_info_image_file', color=self.colorInfo)
            
            dpg.add_drawlist(id='render_ct', width=self.ctDrawWidth, height=self.ctDrawHeight)
            dpg.draw_polygon(parent='render_ct', points=[(0, 0), (self.ctDrawWidth, 0), (self.ctDrawWidth, self.ctDrawHeight), 
                             (0, self.ctDrawHeight), (0, 0)], color=(255, 255, 255, 255))

            dpg.add_same_line(spacing=0)

            dpg.add_drawlist(id='render_labels', width=self.ctDrawWidth, height=self.ctDrawHeight)
            dpg.draw_polygon(parent='render_labels', points=[(0, 0), (self.ctDrawWidth, 0), (self.ctDrawWidth, self.ctDrawHeight), 
                             (0, self.ctDrawHeight), (0, 0)], color=(255, 255, 255, 255))

            dpg.add_slider_int(default_value=0, min_value=0, max_value=0, width=self.ctDrawWidth,
                               callback=self.callBackSlicerCT, id='slicerCT')

            dpg.add_same_line(spacing=0)

            dpg.add_text('No labels', id='txt_info_label_file', color=self.colorInfo)

            ####################################################################
            
            with dpg.group(id='groupStep2', show=False):
                dpg.add_separator()

                dpg.add_text('Step 2', color=self.colorTitle)
                dpg.add_text('Imaging system parameters:')
                dpg.add_drawlist(id='render_carm_left', width=self.carmDrawWidth, height=self.carmDrawHeight)
                # Frame
                dpg.draw_polygon(parent='render_carm_left', points=[(0, 0), (self.carmDrawWidth, 0), (self.carmDrawWidth, self.carmDrawHeight), 
                                (0, self.carmDrawHeight), (0, 0)], color=(255, 255, 255, 255))         

                dpg.add_same_line(spacing=0)
                dpg.add_drawlist(id='render_carm_top', width=self.carmDrawWidth, height=self.carmDrawHeight)
                # Frame
                dpg.draw_polygon(parent='render_carm_top', points=[(0, 0), (self.carmDrawWidth, 0), (self.carmDrawWidth, self.carmDrawHeight), 
                                (0, self.carmDrawHeight), (0, 0)], color=(255, 255, 255, 255))

                dpg.add_same_line(spacing=0)
                dpg.add_drawlist(id='render_carm_ddr', width=self.carmDrawWidth, height=self.carmDrawHeight)
                # Frame
                dpg.draw_polygon(parent='render_carm_ddr', points=[(0, 0), (self.carmDrawWidth, 0), (self.carmDrawWidth, self.carmDrawHeight), 
                                (0, self.carmDrawHeight), (0, 0)], color=(255, 255, 255, 255))


                dpg.add_text('LAO')
                dpg.add_same_line(spacing=10)
                dpg.add_slider_float(default_value=0, min_value=-40, max_value=40, 
                                    format="%.0f deg", callback=self.callBackLAORAO, id='sliderLAORAO')
                dpg.add_same_line(spacing=10)
                dpg.add_text('RAO')

                dpg.add_text('CAU')
                dpg.add_same_line(spacing=10)
                dpg.add_slider_float(default_value=0, min_value=-40, max_value=40, 
                                    format="%.0f deg", callback=self.callBackCAUCRA, id='sliderCAUCRA')
                dpg.add_same_line(spacing=10)
                dpg.add_text('CRA')

                dpg.add_text('Trans X')
                dpg.add_same_line(spacing=10)
                dpg.add_slider_float(default_value=0, min_value=-100, max_value=100, 
                                    format="%.0f mm", callback=self.callBackTransX, id='sliderTX')

                dpg.add_text('Trans Y')
                dpg.add_same_line(spacing=10)
                dpg.add_slider_float(default_value=0, min_value=-100, max_value=100, 
                                    format="%.0f mm", callback=self.callBackTransY, id='sliderTY')

                dpg.add_text('Trans Z')
                dpg.add_same_line(spacing=10)
                dpg.add_slider_float(default_value=0, min_value=-100, max_value=100, 
                                    format="%.0f mm", callback=self.callBackTransZ, id='sliderTZ')

                dpg.add_text('Tube voltage')
                dpg.add_same_line(spacing=10)
                dpg.add_input_float(default_value=self.fluoEnergy, min_value=40, max_value=140, width=200,
                                    format="%.2f kV", step=1, callback=self.callBackVoltage, id='inputVoltage')
                
                dpg.add_text('Beam aperture')
                dpg.add_same_line(spacing=10)
                dpg.add_input_float(default_value=10, min_value=5, max_value=15, width=200,
                                    format="%.1f deg", step=1, id='inputAperture')
                
                dpg.add_button(label='Reset', callback=self.callBackResetCarm)
                dpg.add_same_line(spacing=10)
                dpg.add_button(label='Get DDR', callback=self.callBackGetDDR)

            ####################################################################

            with dpg.group(id='groupStep3', show=False):
                dpg.add_separator()

                dpg.add_text('Step 3', color=self.colorTitle)
                dpg.add_text('Simulation parameters:')

                dpg.add_text('GPU id')
                dpg.add_same_line(spacing=10)
                dpg.add_input_int(default_value=2, min_value=-1, max_value=5, step=1, 
                                  width=100, id='inputGPUID')
                                  #callback=self.callBackVoltage, id='inputVoltage')

                dpg.add_text('Number of particles:')
                dpg.add_same_line(spacing=10)
                dpg.add_input_int(default_value=1, min_value=1, max_value=1000, step=1, 
                                  width=100, id='inputNbParticles')
                dpg.add_same_line(spacing=10)
                dpg.add_text('x10^6')

                dpg.add_text('Used TLE:')
                dpg.add_same_line(spacing=10)
                dpg.add_checkbox(default_value=True, id='checkTLE')

                dpg.add_button(label='Run', width=100, height=50, callback=self.callBackRunGGEMS)

                dpg.add_drawlist(id='render_dose', width=self.ctDrawWidth, height=self.ctDrawHeight)
                dpg.draw_polygon(parent='render_dose', points=[(0, 0), (self.ctDrawWidth, 0), (self.ctDrawWidth, self.ctDrawHeight), 
                                (0, self.ctDrawHeight), (0, 0)], color=(255, 255, 255, 255))

                dpg.add_same_line(spacing=0)

                dpg.add_drawlist(id='render_proj', width=self.ctDrawWidth, height=self.ctDrawHeight)
                dpg.draw_polygon(parent='render_proj', points=[(0, 0), (self.ctDrawWidth, 0), (self.ctDrawWidth, self.ctDrawHeight), 
                                (0, self.ctDrawHeight), (0, 0)], color=(255, 255, 255, 255))

                ### Table
                dpg.add_table(header_row=True, id='tableResults')
                dpg.add_table_column(parent='tableResults', label='Label')
                dpg.add_table_column(parent='tableResults', label='Dose [Gy]')
                dpg.add_table_column(parent='tableResults', label='Uncertainty')

                
                

            ########## Popup ################################
            with dpg.window(label='Info', pos=(self.mainWinWidth//4, self.mainWinHeight//2), width=self.mainWinWidth//2, # height=self.mainWinHeight, pos=(0, 0), no_background=True,
                            no_move=True, no_resize=True, no_collapse=True, no_close=True, no_title_bar=True,
                            id='infoWindow', show=False):
                dpg.add_text('Message...', id='txtInfo')

        self.firstCarmDraw()
        self.updateCarmDraw()
        dpg.start_dearpygui()

if __name__ == '__main__':
    App = MainApp()
    App.show()