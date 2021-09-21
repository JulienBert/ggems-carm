import dearpygui.dearpygui as dpg
from tools import importMHD, array2image
import matplotlib.pyplot as plt

class MainApp():
    def __init__(self):
        vp = dpg.create_viewport(title='GGEMS C-Arm', width=1920, height=1080, clear_color=(39, 44, 53, 255)) # create viewport takes in config options too!
        dpg.setup_dearpygui(viewport=vp)
        dpg.show_viewport(vp)

        with dpg.file_dialog(directory_selector=False, show=False, callback=self.open_mhd, id='file_dialog_id'):
            dpg.add_file_extension(".mhd", color=(255, 255, 0, 255))

        self.colorTitle = (15, 157, 255, 255)  # Blue
        self.colorInfo = (255, 255, 0, 255)  # Yellow

        self.colormap = range(0, 255, 1)

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

            image = array2image(self.arrayRaw[nz//2], self.colormap)

            print(image)

            with dpg.window(label='Image slice', width=nx, height=ny):
                dpg.add_static_texture(nx, ny, image, id='slice_image')

            
        else:
            pass

    def show(self):
        with dpg.window(label='Main Window', width=500, height=1080, pos=(0, 0), 
                        no_move=True, no_resize=True, no_collapse=True, no_close=True, no_title_bar=True):
            dpg.add_text('Step 1', color=self.colorTitle)
            
            dpg.add_text('Select a patient file:')
            dpg.add_same_line(spacing=10)
            dpg.add_button(label='Open...', callback=lambda: dpg.show_item('file_dialog_id'))
            dpg.add_text('No file', id='txt_info_image_file', color=self.colorInfo)

        

        dpg.start_dearpygui()

if __name__ == '__main__':
    App = MainApp()
    App.show()