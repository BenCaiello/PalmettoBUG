''' 
This is a launching point for the GUI, that calls the main App class and initiates the GUI loop
It also serves as a ``central`` place for modifying / filtering warnings & logging from the program
'''

## Legend has it that PalmettoBUG stands for:
# "(P)ALMETTO: (A)cronym (L)onger (M)ore (E)ven (T)han (T)he (O)riginal, (B)etter (U)ser (G)UI", but these rumors I can neither confirm nor deny. 

# SoliDeoGloria

import warnings

warnings.filterwarnings("ignore", message = "The legacy Dask DataFrame implementation is deprecated") 
warnings.filterwarnings("ignore", message = "Transforming to str index")   ## anndata implicit modification warning that is not necessary
warnings.filterwarnings("ignore", message = "Observation names are not unique")  ## anndata UserWarning that is not necessary
warnings.filterwarnings("ignore", message = "Passing a BlockManager")    # deprecated in pandas warning (suddenly showed up 9-6-24 --> tighten down dependency list!)
warnings.filterwarnings("ignore", message = "nopython is set for njit")   # irrelevant warning from dependencies (squidpy / numba)
warnings.filterwarnings("ignore", message = "Setting an item of incompatible dtype is deprecated")    ## its a future warning and it is difficult to resolve -- pandas 
                                                                                                            # does not seem to support in-place casting of dtypes (in the future)?
                                                                                                            # seems like it would require creating a new column with the
                                                                                                            # new dtype, then deleting the old column to get the effect
                                                                                                            # I want without the warning -- but that is a pain and extra code / steps.
from .Entrypoint.app_and_entry import App # noqa: E402

__all__ = ["run_GUI"]
# import logging


#### These final code blocks execute the program
def run_GUI() -> None:
    '''Launches the PalmettoBUG GUI '''
    App1 = App(None)
    App1.mainloop()

if __name__ == "__main__":
    run_GUI()



