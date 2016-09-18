import logging
import sys
from clueslib.platform import PowerManager_cmdline
import cpyutils.config

_LOGGER=logging.getLogger("[DMACHINE]")

try:
    config_dmachine
except:
    config_dmachine = cpyutils.config.Configuration(
        "DMACHINE",
        {
            "DMACHINE_CMDLINE_POWON": "/usr/local/bin/docker-machine start %%h",
            "DMACHINE_CMDLINE_POWOFF": "/usr/local/bin/docker-machine stop %%h "
        }

class powermanager(PowerManager_cmdline):
    def __init__(self):
        PowerManager_cmdline.__init__(self, config_dmachine.DMACHINE_CMDLINE_POWON, config_dmachine.DMACHINE_CMDLINE_POWOFF)
