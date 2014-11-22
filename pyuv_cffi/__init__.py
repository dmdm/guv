"""pyuv_cffi - an implementation of pyuv via CFFI

Compatible with Python 3 and pypy3
"""
import os

import cffi
import cffi.verifier

# clean up old compiled library binaries (not needed in production?)
cffi.verifier.cleanup_tmpdir()

# load FFI definitions and custom C code
ffi = cffi.FFI()
with open(os.path.join(os.path.dirname(__file__), 'pyuv_cffi_cdef.c')) as f:
    ffi.cdef(f.read())

with open(os.path.join(os.path.dirname(__file__), 'pyuv_cffi.c')) as f:
    libuv = ffi.verify(f.read(), libraries=['uv'])


class Loop:
    def __init__(self):
        self.loop_h = libuv.pyuv_loop_new()
        self._loop_h_allocated = True

    @classmethod
    def default_loop(cls):
        loop = Loop.__new__(cls)
        loop.loop_h = libuv.uv_default_loop()
        loop.loop_h_allocated = False  # the default loop can't be freed
        return loop

    @property
    def alive(self):
        return bool(libuv.uv_loop_alive(self.loop_h))

    def close(self):
        self._free()

    def run(self, mode=libuv.UV_RUN_DEFAULT):
        return libuv.uv_run(self.loop_h, mode)

    def stop(self):
        libuv.uv_stop(self.loop_h)

    def _free(self):
        if self._loop_h_allocated:
            libuv.pyuv_loop_del(self.loop_h)
            self._loop_h_allocated = False

    def __del__(self):
        # free the memory allocated by libuv.pyuv_loop_new()
        self.close()


class Handle:
    def __init__(self):
        self._ref = False

    @property
    def ref(self):
        return self._ref

    @ref.setter
    def ref(self, value):
        if value:
            # set ref on this handle
            pass
        else:
            # remove ref on this handle
            pass


class Signal(Handle):
    def __init__(self, loop):
        super().__init__()
        self.loop = loop

        self.sig_h = libuv.pyuv_signal_new(loop.loop_h)
        self._sig_h_allocated = True

        self._ffi_cb = None  # FFI callbacks need to be kept alive in order to be valid

    def start(self, callback, sig_num):
        """Start the signal handle

        :type callback: Callable(sig_handle: Signal, sig_num: int)
        :type sig_num: int
        """

        def cb_wrapper(uv_signal_t, signum):
            callback(self, signum)

        ffi_cb = ffi.callback('void(*)(uv_signal_t *, int)', cb_wrapper)
        self._ffi_cb = ffi_cb  # keep the FFI cdata object alive as long as this instance is alive
        libuv.uv_signal_start(self.sig_h, ffi_cb, sig_num)

    def stop(self):
        self._ffi_cb = None  # remove reference to the cdata object (it will be freed automatically)
        libuv.uv_signal_stop(self.sig_h)

    def _free(self):
        self._ffi_cb = None
        if self._sig_h_allocated:
            libuv.pyuv_signal_del(self.sig_h)
            self._sig_h_allocated = False

    def __del__(self):
        self.stop()
        self._free()


class Poll(Handle):
    def __init__(self, loop, fd):
        super().__init__()
        self._poll_handle = libuv.pyuv_poll_new(loop.loop_h, fd)

    def start(self, events, cb):
        return NotImplemented

    def stop(self):
        return NotImplemented


def sig_cb(sig_h, sig_num):
    print('sig_cb({}, {})'.format(sig_h, sig_num))
    sig_h.stop()
    sig_h.loop.stop()


def run():
    import signal

    loop = Loop()
    sig_h = Signal(loop)
    sig_h.start(sig_cb, signal.SIGINT)
    status = loop.run()
    print('loop.run() -> ', status)