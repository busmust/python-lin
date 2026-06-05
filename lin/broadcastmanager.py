# coding: utf-8

"""
Exposes several methods for transmitting cyclic messages.

The main entry point to these classes should be through
:meth:`lin.BusABC.send_periodic`.
"""

import abc
import logging
import threading
import time
import warnings

log = logging.getLogger('lin.bcm')


class CyclicTask(object):
    """
    Abstract Base for all cyclic tasks.
    """

    @abc.abstractmethod
    def stop(self):
        """Cancel this periodic task.

        :raises lin.LinError:
            If stop is called on an already stopped task.
        """


class CyclicSendTaskABC(CyclicTask):
    """
    Message send task with defined period
    """

    def __init__(self, message, period):
        """
        :param lin.Message message: The message to be sent periodically.
        :param float period: The rate in seconds at which to send the message.
        """
        self.message = message
        self.lin_id = message.lin_id
        self.period = period
        super(CyclicSendTaskABC, self).__init__()


class LimitedDurationCyclicSendTaskABC(CyclicSendTaskABC):

    def __init__(self, message, period, duration):
        """Message send task with a defined duration and period.

        :param lin.Message message: The message to be sent periodically.
        :param float period: The rate in seconds at which to send the message.
        :param float duration:
            The duration to keep sending this message at given rate.
        """
        super(LimitedDurationCyclicSendTaskABC, self).__init__(message, period)
        self.duration = duration


class RestartableCyclicTaskABC(CyclicSendTaskABC):
    """Adds support for restarting a stopped cyclic task"""

    @abc.abstractmethod
    def start(self):
        """Restart a stopped periodic task.
        """


class ModifiableCyclicTaskABC(CyclicSendTaskABC):
    """Adds support for modifying a periodic message"""

    def modify_data(self, message):
        """Update the contents of this periodically sent message without altering
        the timing.

        :param lin.Message message:
          The message with the new :attr:`lin.Message.data`.
          Note: The arbitration ID cannot be changed.
        """
        self.message = message


class MultiRateCyclicSendTaskABC(CyclicSendTaskABC):
    """A Cyclic send task that supports switches send frequency after a set time.
    """

    def __init__(self, channel, message, count, initial_period, subsequent_period):
        """
        Transmits a message `count` times at `initial_period` then continues to
        transmit message at `subsequent_period`.

        :param channel: See interface specific documentation.
        :param lin.Message message:
        :param int count:
        :param float initial_period:
        :param float subsequent_period:
        """
        super(MultiRateCyclicSendTaskABC, self).__init__(channel, message, subsequent_period)


class ThreadBasedCyclicSendTask(ModifiableCyclicTaskABC,
                                LimitedDurationCyclicSendTaskABC,
                                RestartableCyclicTaskABC):
    """Fallback cyclic send task using thread."""

    def __init__(self, bus, lock, message, period, duration=None):
        super(ThreadBasedCyclicSendTask, self).__init__(message, period, duration)
        self.bus = bus
        self.lock = lock
        self.stopped = True
        self.thread = None
        self.end_time = time.time() + duration if duration else None
        self.start()

    def stop(self):
        self.stopped = True
        time.sleep(self.period)

    def start(self):
        self.stopped = False
        if self.thread is None or not self.thread.is_alive():
            name = "Cyclic send task for 0x%X" % (self.message.lin_id)
            self.thread = threading.Thread(target=self._run, name=name)
            self.thread.daemon = True
            self.thread.start()

    def _run(self):
        while not self.stopped:
            # Prevent calling bus.send from multiple threads
            with self.lock:
                started = time.time()
                try:
                    self.bus.send(self.message)
                except Exception as exc:
                    log.exception(exc)
                    break
            if self.end_time is not None and time.time() >= self.end_time:
                break
            # Compensate for the time it takes to send the message
            delay = self.period - (time.time() - started)
            time.sleep(max(0.0, delay))
        self.bus.cancel_send()


def send_periodic(bus, message, period, *args, **kwargs):
    """
    Send a :class:`~lin.Message` every `period` seconds on the given bus.

    :param lin.BusABC bus: A LIN bus which supports sending.
    :param lin.Message message: Message to send periodically.
    :param float period: The minimum time between sending messages.
    :return: A started task instance
    """
    warnings.warn("The function `lin.send_periodic` is deprecated and will " +
                  "be removed in an upcoming version. Please use `lin.Bus.send_periodic` instead.", DeprecationWarning)
    return bus.send_periodic(message, period, *args, **kwargs)