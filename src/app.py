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

        ### Config C-arm (ref uses image frame)
        #
        # Source
        self.carmDistISOSource = 400
        self.carmPosSource = np.matrix([[0],
                                        [-self.carmDistISOSource],
                                        [0]], 'float32')
        # Flat panel
        self.carmDistISOPanel = dp = 600
        self.flatPanelHalfSize = hs = 200 # flatPanelHalfSize
        self.carmPosPointsPanel = np.matrix([[-hs, hs, hs, -hs],
                                             [dp, dp, dp, dp],
                                             [hs, hs, -hs, -hs]], 'float32')
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

    def callBackCAUCRA(self, sender, app_data):
        pass

    def callBackTransX(self, sender, app_data):
        self.carmTranslation[0][0] = app_data
    
    def callBackTransY(self, sender, app_data):
        self.carmTranslation[1][0] = app_data

    def callBackTransZ(self, sender, app_data):
        self.carmTranslation[2][0] = app_data

    def callBackResetCarm(self, sender, app_data):
        pass

    def callBackVoltage(self, sender, app_data):
        pass

    def callBackTestCarm(self):
        d = 2.5
        cx, cy = 100, 100

        # Source
        dpg.draw_triangle(parent='render_carm_top', p1=(cx, cy-d), p2=(cx+d, cy+d), p3=(cx-d, cy+d), color=self.colorSource)

    def updateCarmConf(self):
        pass

    def show(self):
        with dpg.window(label='Main Window', width=500, height=1080, pos=(0, 0), no_background=True,
                        no_move=True, no_resize=True, no_collapse=True, no_close=True, no_title_bar=True):
            dpg.add_text('Step 1', color=self.colorTitle)
            
            dpg.add_text('Select a patient file:')
            dpg.add_same_line(spacing=10)
            dpg.add_button(label='Open...', callback=lambda: dpg.show_item('file_dialog_id'))
            dpg.add_text('No file', id='txt_info_image_file', color=self.colorInfo)
            dpg.add_drawlist(id='render_ct', width=200, height=200)

            dpg.add_text('Step 2', color=self.colorTitle)
            dpg.add_text('Imaging system parameters:')
            dpg.add_drawlist(id='render_carm_left', width=200, height=200)
            dpg.add_same_line(spacing=0)
            dpg.add_drawlist(id='render_carm_top', width=200, height=200)

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
            dpg.add_button(label='Test', callback=self.callBackTestCarm)


        dpg.start_dearpygui()

if __name__ == '__main__':
    App = MainApp()
    App.show()