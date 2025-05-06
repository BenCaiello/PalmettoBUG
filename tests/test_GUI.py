import os
import palmettobug
from palmettobug.Entrypoint.app_and_entry import App

#homedir = __file__.replace("\\","/")
#homedir = homedir[:(homedir.rfind("/"))]
#homedir = homedir[:(homedir.rfind("/"))]
#fetch_dir = homedir + "/GUI_test"
#if not os.path.exists(fetch_dir):
#    os.mkdir(fetch_dir)
#proj_directory = fetch_dir + "/Example_IMC"

#def test_fetch_IMC():
#   fetch_IMC_example(fetch_dir)

def test_setup_app():
    global app
    app = App(None)
    assert True   ## non-failure is enough for me right now, as it implies successful setting up of the widgets of the GUI

def test_toggle_in_gui():
    palmettobug.ImageProcessing.ImageAnalysisClass.toggle_in_gui()   ## really here to reset --> not being in the gui after testing the App above

#def test_load_IMC():
#    app.entrypoint.img_entry_func(fetch_dir, [1.0,1.0], from_mcds = True)
#    assert True   ## non-failure is enough for me right now