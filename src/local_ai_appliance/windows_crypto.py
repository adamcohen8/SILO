"""Windows CNG AES-GCM. Module validation remains configuration-specific evidence.

Uses the named Microsoft Primitive Provider instead of a wheel's OpenSSL build.
This does not itself claim a FIPS certificate or validate disk/key protection.
"""
import ctypes as C
import os

from .folders import AccessDenied


class AuthInfo(C.Structure):
    _fields_ = [('size', C.c_uint32), ('version', C.c_uint32),
                ('nonce', C.c_void_p), ('nonce_size', C.c_uint32),
                ('aad', C.c_void_p), ('aad_size', C.c_uint32),
                ('tag', C.c_void_p), ('tag_size', C.c_uint32),
                ('mac', C.c_void_p), ('mac_size', C.c_uint32),
                ('aad_total', C.c_uint32), ('data_total', C.c_uint64), ('flags', C.c_uint32)]


class WindowsAESGCM:
    def __init__(self, key):
        if os.name != 'nt' or not isinstance(key, bytes) or len(key) != 32:
            raise AccessDenied('Windows project encryption requires a 256-bit key')
        self.dll = C.WinDLL('bcrypt', use_last_error=True)
        self.algorithm, self.key = C.c_void_p(), C.c_void_p()
        bind = lambda name, result, args: self._bind(name, result, args)
        bind('BCryptOpenAlgorithmProvider', C.c_int32, [C.POINTER(C.c_void_p), C.c_wchar_p, C.c_wchar_p, C.c_uint32])
        bind('BCryptSetProperty', C.c_int32, [C.c_void_p, C.c_wchar_p, C.c_void_p, C.c_uint32, C.c_uint32])
        bind('BCryptGetProperty', C.c_int32, [C.c_void_p, C.c_wchar_p, C.c_void_p, C.c_uint32, C.POINTER(C.c_uint32), C.c_uint32])
        bind('BCryptGenerateSymmetricKey', C.c_int32, [C.c_void_p, C.POINTER(C.c_void_p), C.c_void_p, C.c_uint32, C.c_void_p, C.c_uint32, C.c_uint32])
        for name in ('BCryptEncrypt', 'BCryptDecrypt'):
            bind(name, C.c_int32, [C.c_void_p, C.c_void_p, C.c_uint32, C.c_void_p, C.c_void_p,
                                 C.c_uint32, C.c_void_p, C.c_uint32, C.POINTER(C.c_uint32), C.c_uint32])
        bind('BCryptDestroyKey', C.c_int32, [C.c_void_p])
        bind('BCryptCloseAlgorithmProvider', C.c_int32, [C.c_void_p, C.c_uint32])
        self.key_object = None
        try:
            self._ok(self.dll.BCryptOpenAlgorithmProvider(C.byref(self.algorithm), 'AES', 'Microsoft Primitive Provider', 0))
            mode = C.create_unicode_buffer('ChainingModeGCM')
            self._ok(self.dll.BCryptSetProperty(self.algorithm, 'ChainingMode', mode, C.sizeof(mode), 0))
            length, written = C.c_uint32(), C.c_uint32()
            self._ok(self.dll.BCryptGetProperty(self.algorithm, 'ObjectLength', C.byref(length), 4, C.byref(written), 0))
            if not 0 < length.value <= 65536 or written.value != 4:
                raise AccessDenied('Windows cryptographic provider returned invalid metadata')
            self.key_object = C.create_string_buffer(length.value)
            secret = C.create_string_buffer(key)
            try:
                self._ok(self.dll.BCryptGenerateSymmetricKey(self.algorithm, C.byref(self.key),
                    self.key_object, len(self.key_object), secret, len(key), 0))
            finally: C.memset(secret, 0, C.sizeof(secret))
        except BaseException:
            self.close(); raise

    def _bind(self, name, result, arguments):
        function = getattr(self.dll, name)
        function.restype, function.argtypes = result, arguments

    @staticmethod
    def _ok(status):
        if status < 0: raise AccessDenied('Windows authenticated encryption failed')

    def _crypt(self, nonce, data, aad, *, decrypt):
        if (not self.key.value or not isinstance(nonce, bytes) or len(nonce) != 12
                or not isinstance(data, bytes) or not isinstance(aad, bytes)
                or len(data) > 64 * 1024 * 1024 + (16 if decrypt else 0)
                or len(aad) > 65536 or decrypt and len(data) < 16):
            raise AccessDenied('Invalid authenticated encryption inputs')
        clear_size = len(data) - 16 if decrypt else len(data)
        source = C.create_string_buffer(data[:clear_size] if decrypt else data)
        nonce_buffer, aad_buffer = C.create_string_buffer(nonce), C.create_string_buffer(aad)
        tag = C.create_string_buffer(data[-16:] if decrypt else bytes(16), 16)
        info = AuthInfo()
        info.size, info.version = C.sizeof(AuthInfo), 1
        info.nonce, info.nonce_size = C.cast(nonce_buffer, C.c_void_p), len(nonce)
        info.aad, info.aad_size = C.cast(aad_buffer, C.c_void_p), len(aad)
        info.tag, info.tag_size = C.cast(tag, C.c_void_p), 16
        output = C.create_string_buffer(max(1, clear_size))
        written = C.c_uint32()
        operation = self.dll.BCryptDecrypt if decrypt else self.dll.BCryptEncrypt
        try:
            self._ok(operation(self.key, source, clear_size, C.byref(info), None, 0,
                               output, clear_size, C.byref(written), 0))
            if written.value != clear_size: raise AccessDenied('Unexpected Windows encryption output')
            return output.raw[:written.value] + (b'' if decrypt else tag.raw)
        finally:
            C.memset(source, 0, C.sizeof(source)); C.memset(output, 0, C.sizeof(output))

    def encrypt(self, nonce, data, aad): return self._crypt(nonce, data, aad, decrypt=False)
    def decrypt(self, nonce, data, aad): return self._crypt(nonce, data, aad, decrypt=True)

    def close(self):
        if self.key.value:
            self.dll.BCryptDestroyKey(self.key); self.key = C.c_void_p()
        if self.key_object is not None: C.memset(self.key_object, 0, C.sizeof(self.key_object))
        if self.algorithm.value:
            self.dll.BCryptCloseAlgorithmProvider(self.algorithm, 0); self.algorithm = C.c_void_p()

    def __del__(self):
        try: self.close()
        except Exception: pass


def recovery_key(password, salt):
    if os.name != 'nt' or not isinstance(password, bytes) or not isinstance(salt, bytes) or len(salt) != 16:
        raise AccessDenied('Invalid native recovery key inputs')
    dll = C.WinDLL('bcrypt')
    dll.BCryptOpenAlgorithmProvider.argtypes = [C.POINTER(C.c_void_p), C.c_wchar_p, C.c_wchar_p, C.c_uint32]
    dll.BCryptOpenAlgorithmProvider.restype = C.c_int32
    dll.BCryptDeriveKeyPBKDF2.argtypes = [C.c_void_p, C.c_void_p, C.c_uint32, C.c_void_p, C.c_uint32,
                                       C.c_uint64, C.c_void_p, C.c_uint32, C.c_uint32]
    dll.BCryptDeriveKeyPBKDF2.restype = C.c_int32
    dll.BCryptCloseAlgorithmProvider.argtypes = [C.c_void_p, C.c_uint32]
    dll.BCryptCloseAlgorithmProvider.restype = C.c_int32
    handle = C.c_void_p()
    secret, salt_buffer, output = C.create_string_buffer(password), C.create_string_buffer(salt), C.create_string_buffer(32)
    try:
        WindowsAESGCM._ok(dll.BCryptOpenAlgorithmProvider(C.byref(handle), 'SHA256', 'Microsoft Primitive Provider', 8))
        WindowsAESGCM._ok(dll.BCryptDeriveKeyPBKDF2(handle, secret, len(password), salt_buffer, len(salt),
                                                  600_000, output, 32, 0))
        return output.raw
    finally:
        C.memset(secret, 0, C.sizeof(secret)); C.memset(output, 0, C.sizeof(output))
        if handle.value: dll.BCryptCloseAlgorithmProvider(handle, 0)
