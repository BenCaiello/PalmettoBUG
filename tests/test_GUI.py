import os

import palmettobug
from palmettobug.Entrypoint.app_and_entry import App, fetch_IMC_example, fetch_CyTOF_example

homedir = __file__.replace("\\","/")
homedir = homedir[:(homedir.rfind("/"))]
homedir = homedir[:(homedir.rfind("/"))]
fetch_dir = homedir + "/project_folder"
if not os.path.exists(fetch_dir):
    os.mkdir(fetch_dir)
proj_directory = fetch_dir + "/Example_IMC"

##>>## GUI App & entrypoint tests
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
    assert True 

def test_call_configGUI():
    app.entrypoint.call_configGUI()
    assert True 

def test_launchExampleDataWindow():
    app.entrypoint.launchExampleDataWindow()
    assert True

def test_img_entry_func():
    number = app.entrypoint.img_entry_func(proj_directory)  ## successfully proceeding through function in tests
    assert True

def test_FCS_choice():
    app.entrypoint.FCS_choice(fetch_dir + "/Example_CyTOF")
    assert True  


##>>## GUI Image Analysis tests
def test_call_raw_to_img_part_1_hpf():
    app.entrypoint.image_proc_widg.call_raw_to_img_part_1_hpf()
    assert True   

def test_call_mask_expand():
    app.entrypoint.image_proc_widg.call_mask_expand()
    assert True 


def test_call_region_measurement():
    app.entrypoint.image_proc_widg.call_region_measurement()
    assert True 

def test_call_to_Analysis():
    app.entrypoint.image_proc_widg.call_to_Analysis()
    assert True 

def test_go_to_Analysis_window():
    app.entrypoint.image_proc_widg.go_to_Analysis_window(fetch_dir + "/Example_CyTOF")
    assert True 


def test_toggle_in_gui():
    palmettobug.ImageProcessing.ImageAnalysisClass.toggle_in_gui()   ## really here to reset --> not being in the gui after testing the App above


'''
##>>## GUI Pixel classification tests

def test_px_widg_connection():
    app.Tabs.px_classification.create.px_widg
    assert True 



'''