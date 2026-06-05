# coding: utf-8

"""Notifier that dispatches bus messages to listeners."""

import logging
import threading

from .listener import Listener

LOG = logging.getLogger(__name__)


class Notifier(object):
    """Receive messages from a bus and fan out to listeners."""

    def __init__(self, bus, listeners, timeout=1.0):
        self.bus = bus
        self.listeners = list(listeners or [])
        self.timeout = timeout
        self._running = True
        self._thread = threading.Thread(target=self._rx_thread, name='lin-notifier')
        self._thread.daemon = True
        self._thread.start()

    def add_listener(self, listener):
        self.listeners.append(listener)

    def remove_listener(self, listener):
        self.listeners.remove(listener)

    def _dispatch(self, msg):
        for listener in list(self.listeners):
            try:
                if isinstance(listener, Listener):
                    listener.on_message_received(msg)
                else:
                    listener(msg)
            except Exception:
                LOG.exception('Error in listener callback')

    def _rx_thread(self):
        while self._running:
            try:
                msg = self.bus.recv(self.timeout)
                if msg is not None:
                    self._dispatch(msg)
            except Exception:
                LOG.exception('Error while receiving from bus')
                break

    def stop(self, timeout=5.0):
        self._running = False
        if self._thread.is_alive():
            self._thread.join(timeout)
        for listener in self.listeners:
            try:
                stop = getattr(listener, 'stop', None)
                if callable(stop):
                    stop()
            except Exception:
                LOG.exception('Error while stopping listener')
