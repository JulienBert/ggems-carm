import dearpygui.dearpygui as dpg
from tools import importMHD, array2image
import matplotlib.pyplot as plt
import numpy as np

class MainApp():
    def __init__(self):
        vp = dpg.create_viewport(title='GGEMS C-Arm', width=500, height=1080, clear_color=(39, 44, 53, 255)) # create viewport takes in config options too!
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

        # Change to draw frame
        self.panelFrame = np.matrix([[self.carmDrawWidth//2],
                                     [self.carmDrawHeight//2],
                                     [0]], 'float32')

        ### Config C-arm (ref uses image frame)
        #
        # Source
        self.carmDistISOSource = 400
        self.carmOrgPosSource = np.matrix([[0],
                                           [self.carmDistISOSource],
                                           [0]], 'float32')
        self.carmPosSource = np.copy(self.carmOrgPosSource)

        # Flat panel
        self.carmDistISOPanel = dp = 600
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
        scaling = 0.1
        self.carmProjZY = np.matrix([[0,       0, scaling], 
                                     [0, scaling,       0], 
                                     [0,       0,       0]], 'float32')
        # Projection on XZ
        self.carmProjXZ = np.matrix([[scaling, 0,        0], 
                                     [0,       0, -scaling], 
                                     [0,       0,        0]], 'float32')

        # Patient
        self.patientThoraxSize = (600*scaling, 200*scaling)  # mm (length, thickness)
        self.patientHead = (100*scaling)  # radius in mm
        self.patientArm = (100*scaling, 400*scaling, 100*scaling)  # offset, length, thickness in mm


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

            image = array2image(self.arrayRaw[nz//2])

            with dpg.texture_registry():
                dpg.add_static_texture(nx, ny, image, id='texture_ct')

            dpg.draw_image(parent='render_ct', texture_id='texture_ct', pmin=(0, 0), pmax=(2*nx, 2*ny), uv_min=(0, 0), uv_max=(1, 1)) 
            
            # with dpg.window(label='Image slice', width=nx, height=ny):
            #     dpg.add_image("texture_ct")

            
        else:
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
        pass

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
        d = 2.5

        # Frame
        dpg.draw_polygon(parent='render_carm_left', points=[(0, 0), (self.carmDrawWidth, 0), (self.carmDrawWidth, self.carmDrawHeight), 
                                                            (0, self.carmDrawHeight), (0, 0)], color=(255, 255, 255, 255))
        # Isocenter
        cx = self.panelFrame[0][0]
        cy = self.panelFrame[1][0]
        dpg.draw_line(parent='render_carm_left', p1=(cx-d, cy), p2=(cx+d, cy), color=(255, 255, 255, 255))
        dpg.draw_line(parent='render_carm_left', p1=(cx, cy-d), p2=(cx, cy+d), color=(255, 255, 255, 255))
                                                                              
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
        

    def updateCarmDraw(self):
        # Compute new conf
        self.updateCarmConfiguration()

        d = 2.5

        ## Left view
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


    def show(self):
        with dpg.window(label='Main Window', width=500, height=1080, pos=(0, 0), no_background=True,
                        no_move=True, no_resize=True, no_collapse=True, no_close=True, no_title_bar=True):
            dpg.add_text('Step 1', color=self.colorTitle)
            
            dpg.add_text('Select a patient file:')
            dpg.add_same_line(spacing=10)
            dpg.add_button(label='Open...', callback=lambda: dpg.show_item('file_dialog_id'))
            dpg.add_text('No file', id='txt_info_image_file', color=self.colorInfo)
            dpg.add_drawlist(id='render_ct', width=200, height=200)

            dpg.add_separator()
            dpg.add_text('Step 2', color=self.colorTitle)
            dpg.add_text('Imaging system parameters:')
            dpg.add_drawlist(id='render_carm_left', width=self.carmDrawWidth, height=self.carmDrawHeight)         

            dpg.add_same_line(spacing=0)
            dpg.add_drawlist(id='render_carm_top', width=self.carmDrawWidth, height=self.carmDrawHeight)

            dpg.add_text('LAO')
            dpg.add_same_line(spacing=10)
            dpg.add_slider_float(default_value=0, min_value=-40, max_value=40, 
                                 format="%.0f deg", callback=self.callBackLAORAO)
            dpg.add_same_line(spacing=10)
            dpg.add_text('RAO')

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
            dpg.add_slider_float(default_value=80, min_value=40, max_value=140, 
                                 format="%.0f kV", callback=self.callBackVoltage)

            dpg.add_button(label='Reset', callback=self.callBackResetCarm)

        self.firstCarmDraw()
        self.updateCarmDraw()
        dpg.start_dearpygui()

if __name__ == '__main__':
    App = MainApp()
    App.show()