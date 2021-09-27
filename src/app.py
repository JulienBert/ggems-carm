import dearpygui.dearpygui as dpg
from tools import importMHD, array2image
import numpy as np
from fluoroscopy import fluoroscopy

class MainApp():
    def __init__(self):
        self.mainWinWidth = 630
        self.mainWinHeight = 1080

        vp = dpg.create_viewport(title='GGEMS C-Arm', width=self.mainWinWidth, height=self.mainWinHeight, 
                                 clear_color=(39, 44, 53, 255)) # create viewport takes in config options too!
        dpg.setup_dearpygui(viewport=vp)
        dpg.show_viewport(vp)

        with dpg.file_dialog(directory_selector=False, show=False, callback=self.open_mhd, id='file_dialog_id'):
            dpg.add_file_extension(".mhd", color=(255, 255, 0, 255))

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

        # Fluorscopy viewer
        # Flag that determine if the CT have to be reconvert into mumap
        self.fluoRequestMuMap = True
        self.fluoEngine = fluoroscopy()
        self.fluoPanelNx = 256
        self.fluoPanelNy = 256
        self.fluoPanelSx = 2.0
        self.fluoPanelSy = 2.0
        self.fluoEnergy = 80.0

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


    def draw2DArrayTo(self, aImage, target_id, tex_id, nx, ny, width, height):
        image = array2image(aImage)

        with dpg.texture_registry():
            dpg.add_static_texture(nx, ny, image, id=tex_id)

        # Manage ratio and centering
        ratio = nx / ny
        if ratio > 1:
            newWidth = width
            newHeight = width / ratio
            paddingH = (height-newHeight) / 2.0
            paddingW = 0
        elif ratio < 1:
            newWidth = height * ratio
            newHeight = height
            paddingH = 0
            paddingW = (width-newWidth) / 2.0
        else:
            newWidth = width
            newHeight = height
            paddingH = 0
            paddingW = 0

        dpg.draw_image(parent=target_id, texture_id=tex_id, 
                       pmin=(paddingW+1, paddingH+1), 
                       pmax=(paddingW+newWidth-1, paddingH+newHeight-1), 
                       uv_min=(0, 0), uv_max=(1, 1)) 


    def open_mhd(self, sender, app_data):
        # print("Sender: ", sender)
        # print("App Data: ", app_data)

        if app_data['file_name'] != '.mhd':
            self.arrayRaw, self.dictHeader = importMHD(app_data['file_path_name'])
            nx, ny, nz = self.dictHeader['shape']
            sx, sy, sz = self.dictHeader['spacing']
            filename = app_data['file_name']
            txt = '%s   %ix%ix%i pix   %4.2fx%4.2fx%4.2f mm' % (filename, nx, ny, nz, sx, sy, sz)
            dpg.set_value('txt_info_image_file', txt)

            # Convert into texture
            with dpg.texture_registry():
                for iSlice in range(nz):
                    image = array2image(self.arrayRaw[iSlice])
                    dpg.add_static_texture(nx, ny, image, id='CT%i' % iSlice)

                    print('texture', iSlice)

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

            self.ctTexParams['nbSlices'] = nz

            # Configure the slicer and draw the first image
            dpg.configure_item('slicerCT', default_value=nz//2, max_value=nz)
            dpg.draw_image(parent='render_ct', texture_id='CT%i' % (nz//2), 
                           pmin=self.ctTexParams['pMin'], 
                           pmax=self.ctTexParams['pMax'], 
                           uv_min=(0, 0), uv_max=(1, 1),
                           id='imageCT')

            # self.draw2DArrayTo(self.arrayRaw[nz//2], 'render_ct_central', 'texture_ct_central', 
            #                    nx, ny, self.ctDrawWidth, self.ctDrawHeight)

            # self.draw2DArrayTo(self.arrayRaw[:, ny//2, :], 'render_ct_coronal', 'texture_ct_coronal', 
            #                    nx, nz, self.ctDrawWidth, self.ctDrawHeight)

        else:
            pass # TODO

    def callBackSlicerCT(self, sender, app_data):
        dpg.delete_item('imageCT')
        dpg.draw_image(parent='render_ct', texture_id='CT%i' % app_data, 
                       pmin=self.ctTexParams['pMin'], 
                       pmax=self.ctTexParams['pMax'], 
                       uv_min=(0, 0), uv_max=(1, 1),
                       id='imageCT')

    def callBackSlicerMasks(self):
        pass

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
        self.updateCarmDraw()
        pass

    def callBackVoltage(self, sender, app_data):
        self.fluoEnergy = app_data
        # If the energy change the CT have to convert into mumap accordingly
        self.fluoRequestMuMap = True

    def callBackGetDDR(self):
        self.fluoEngine.setPose(self.carmRotX, self.carmRotZ, self.carmTranslation)
        self.fluoEngine.setCamera(self.fluoPanelNx, self.fluoPanelNy, 
                                    self.fluoPanelSx, self.fluoPanelSy, self.carmDistISOPanel)

        if self.fluoRequestMuMap:
            self.fluoEngine.setSource(self.fluoEnergy, self.carmDistISOSource)
            self.fluoEngine.setImage(self.arrayRaw, self.dictHeader)
            self.fluoEngine.computeMuMap()
            self.fluoRequestMuMap = False

        imageDDR = self.fluoEngine.getProjection()

        # self.draw2DArrayTo(imageDDR, 'render_carm_ddr', 'texture_ddr', nx, ny, self.carmDrawWidth, self.carmDrawHeight)


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

            dpg.add_drawlist(id='render_masks', width=self.ctDrawWidth, height=self.ctDrawHeight)
            dpg.draw_polygon(parent='render_masks', points=[(0, 0), (self.ctDrawWidth, 0), (self.ctDrawWidth, self.ctDrawHeight), 
                             (0, self.ctDrawHeight), (0, 0)], color=(255, 255, 255, 255))

            dpg.add_slider_int(default_value=0, min_value=0, max_value=0, width=self.ctDrawWidth,
                               callback=self.callBackSlicerCT, id='slicerCT')

            dpg.add_same_line(spacing=0)

            dpg.add_slider_int(default_value=0, min_value=0, max_value=0, width=self.ctDrawWidth,
                               callback=self.callBackSlicerMasks, id='slicerMasks')

            ####################################################################
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
                                 format="%.0f deg", callback=self.callBackLAORAO)
            dpg.add_same_line(spacing=10)
            dpg.add_text('RAO')
            dpg.add_same_line(spacing=30)
            dpg.add_button(label='Get DDR', callback=self.callBackGetDDR)

            dpg.add_text('CAU')
            dpg.add_same_line(spacing=10)
            dpg.add_slider_float(default_value=0, min_value=-40, max_value=40, 
                                 format="%.0f deg", callback=self.callBackCAUCRA)
            dpg.add_same_line(spacing=10)
            dpg.add_text('CRA')

            dpg.add_text('Trans X')
            dpg.add_same_line(spacing=10)
            dpg.add_slider_float(default_value=0, min_value=-100, max_value=100, 
                                 format="%.0f mm", callback=self.callBackTransX)

            dpg.add_text('Trans Y')
            dpg.add_same_line(spacing=10)
            dpg.add_slider_float(default_value=0, min_value=-100, max_value=100, 
                                 format="%.0f mm", callback=self.callBackTransY)

            dpg.add_text('Trans Z')
            dpg.add_same_line(spacing=10)
            dpg.add_slider_float(default_value=0, min_value=-100, max_value=100, 
                                 format="%.0f mm", callback=self.callBackTransZ)

            dpg.add_text('Tube voltage')
            dpg.add_same_line(spacing=10)
            dpg.add_input_float(default_value=self.fluoEnergy, min_value=40, max_value=140, 
                                format="%.2f kV", step=1, callback=self.callBackVoltage)
            

            dpg.add_button(label='Reset', callback=self.callBackResetCarm)

        self.firstCarmDraw()
        self.updateCarmDraw()
        dpg.start_dearpygui()

if __name__ == '__main__':
    App = MainApp()
    App.show()