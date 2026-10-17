#!/bin/sh
# Fake "air pressure ok" (motion.digital-in-02) for testing without air.
# Undo: halcmd net io-din3-0 motion.digital-in-02 (or restart LinuxCNC).
halcmd unlinkp motion.digital-in-02
halcmd setp motion.digital-in-02 1
