import os
import palmettobug
from palmettobug.Entrypoint.app_and_entry import App

fetch_dir = homedir + "/project_folder"
if not os.path.exists(fetch_dir):
    os.mkdir(fetch_dir)
proj_directory = fetch_dir + "/Example_IMC"
np.random.default_rng(42)

def test_fetch_IMC():
    fetch_IMC_example(fetch_dir)

def test_fetch_CyTOF():
    fetch_CyTOF_example(fetch_dir)

def test_setup_app():
    global app
    app = App(None)
    assert True   ## non-failure is enough for me right now, as it implies successful setting up of the widgets of the GUI

def test_GPL_window():
    app.entrypoint.show_GPL()
    assert True   ## non-failure is enough for me right now, as it implies successful setting up of the widgets of the GUI

def test_call_configGUI():
    app.entrypoint.call_configGUI()
    assert True   ## non-failure is enough for me right now, as it implies successful setting up of the widgets of the GUI

def test_launchExampleDataWindow():
    app.entrypoint.launchExampleDataWindow()
    assert True   ## non-failure is enough for me right now, as it implies successful setting up of the widgets of the GUI

def test_img_entry_func():
    app.entrypoint.img_entry_func(proj_directory)
    assert True   ## non-failure is enough for me right now, as it implies successful setting up of the widgets of the GUI

def test_FCS_choice():
    app.entrypoint.FCS_choice(fetch_dir + "/Example_CyTOF")
    assert True   ## non-failure is enough for me right now, as it implies successful setting up of the widgets of the GUI

def test_toggle_in_gui():
    palmettobug.ImageProcessing.ImageAnalysisClass.toggle_in_gui()   ## really here to reset --> not being in the gui after testing the App above