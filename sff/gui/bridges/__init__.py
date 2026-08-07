# SteaMidra — WebBridge domain modules
# Each sub-module contains implementation functions for a specific
# feature domain. The WebBridge class in web_bridge.py delegates
# its @pyqtSlot methods to these implementations.
#
# Functions are named _bridge_<method_name>(bridge, ...) where
# 'bridge' is the WebBridge instance. Shared helpers live on
# WebBridge itself and are accessed via bridge._helper().
