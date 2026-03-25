"""鐢ㄤ簬鏈湴鎸佷箙鍖栧瘑閽ョ殑鍔犲瘑杈呭姪宸ュ叿銆"""
import os
from pathlib import Path
from cryptography.fernet import Fernet, InvalidToken
from src.config.settings import Settings, ensure_app_dirs

ENCRYPTED_SECRET_PREFIX: str = "enc:v1:"


class SecretEncryptionError(RuntimeError):
    """褰撳凡淇濆瓨鐨勫瘑閽ユ棤娉曡В瀵嗘椂鎶涘嚭銆"""


class LocalSecretCipher:
    """浣跨敤鏂囦欢鎸佷箙鍖栫殑 Fernet 瀵嗛挜瀵规湰鍦板瘑閽ヨ繘琛屽姞瑙ｅ瘑銆"""

    def __init__(self, settings: Settings) -> None:
        """鍒濆鍖栨湰鍦板瘑閽ュ姞瑙ｅ瘑鍣ㄣ€?

        Args:
            settings: 搴旂敤閰嶇疆瀵硅薄銆?
        """

        self.settings: Settings = settings
        ensure_app_dirs(settings)
        self.key_path: Path = settings.resolved_model_config_secret_path
        self._fernet: Fernet | None = None

    def encrypt(self, value: str) -> str:
        """灏嗘槑鏂囧瘑閽ュ姞瀵嗗悗鍐嶅啓鍏ユ湰鍦板瓨鍌ㄣ€"""

        token: bytes = self._get_fernet().encrypt(value.encode("utf-8"))
        return f"{ENCRYPTED_SECRET_PREFIX}{token.decode('utf-8')}"

    def decrypt(self, value: str) -> str:
        """瑙ｅ瘑鎸夊綋鍓嶆牸寮忎繚瀛樼殑瀵嗛挜銆"""

        if not value:
            return ""
        if not value.startswith(ENCRYPTED_SECRET_PREFIX):
            raise SecretEncryptionError("宸蹭繚瀛樼殑 API Key 涓嶆槸褰撳墠鍔犲瘑鏍煎紡锛岃閲嶆柊淇濆瓨涓€娆℃ā鍨嬮厤缃€?")

        token: bytes = value.removeprefix(ENCRYPTED_SECRET_PREFIX).encode("utf-8")
        try:
            return self._get_fernet().decrypt(token).decode("utf-8")
        except InvalidToken as exc:
            raise SecretEncryptionError("鏃犳硶瑙ｅ瘑宸蹭繚瀛樼殑 API Key锛岃閲嶆柊淇濆瓨涓€娆℃ā鍨嬮厤缃€?") from exc

    def is_encrypted(self, value: str | None) -> bool:
        """鍒ゆ柇鎸佷箙鍖栧€兼槸鍚︿娇鐢ㄥ綋鍓嶅姞瀵嗘柟妗堛€"""

        return bool(value and value.startswith(ENCRYPTED_SECRET_PREFIX))

    def _get_fernet(self) -> Fernet:
        """涓烘湰鍦板瘑閽ユ枃浠跺垱寤烘垨澶嶇敤 Fernet 瀹炰緥銆"""

        if self._fernet is None:
            self._fernet = Fernet(self._load_or_create_key())
        return self._fernet

    def _load_or_create_key(self) -> bytes:
        """璇诲彇宸蹭繚瀛樺瘑閽ワ紝鎴栫敓鎴愭柊鐨勬湰鍦板瘑閽ユ枃浠躲€"""

        if self.key_path.exists():
            return self.key_path.read_bytes().strip()

        key: bytes = Fernet.generate_key()
        self.key_path.parent.mkdir(parents=True, exist_ok=True)
        self.key_path.write_bytes(key)
        self._best_effort_harden_permissions(self.key_path)
        return key

    def _best_effort_harden_permissions(self, path: Path) -> None:
        """鍦ㄥ钩鍙版敮鎸佹椂灏介噺鏀剁揣瀵嗛挜鏂囦欢鏉冮檺銆"""

        try:
            os.chmod(path, 0o600)
        except OSError:
            return
    

