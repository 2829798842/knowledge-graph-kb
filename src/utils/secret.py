"""用于本地持久化密钥的加密辅助工具。"""

import os
from pathlib import Path

from cryptography.fernet import Fernet, InvalidToken

from src.config.settings import Settings, ensure_app_dirs

ENCRYPTED_SECRET_PREFIX: str = "enc:v1:"


class SecretEncryptionError(RuntimeError):
    """当已保存的密钥无法解密时抛出。"""


class LocalSecretCipher:
    """使用文件持久化的 Fernet 密钥对本地密钥进行加解密。"""

    def __init__(self, settings: Settings) -> None:
        """初始化本地密钥加解密器。

        Args:
            settings: 应用配置对象。
        """

        self.settings: Settings = settings
        ensure_app_dirs(settings)
        self.key_path: Path = settings.resolved_model_config_secret_path
        self._fernet: Fernet | None = None

    def encrypt(self, value: str) -> str:
        """将明文密钥加密后再写入本地存储。"""

        token: bytes = self._get_fernet().encrypt(value.encode("utf-8"))
        return f"{ENCRYPTED_SECRET_PREFIX}{token.decode('utf-8')}"

    def decrypt(self, value: str) -> str:
        """解密按当前格式保存的密钥。"""

        if not value:
            return ""
        if not value.startswith(ENCRYPTED_SECRET_PREFIX):
            raise SecretEncryptionError(
                "已保存的 API Key 不是当前加密格式，请重新保存一次模型配置。"
            )

        token: bytes = value.removeprefix(ENCRYPTED_SECRET_PREFIX).encode("utf-8")
        try:
            return self._get_fernet().decrypt(token).decode("utf-8")
        except InvalidToken as exc:
            raise SecretEncryptionError(
                "无法解密已保存的 API Key，请重新保存一次模型配置。"
            ) from exc

    def is_encrypted(self, value: str | None) -> bool:
        """判断持久化值是否使用当前加密方案。"""

        return bool(value and value.startswith(ENCRYPTED_SECRET_PREFIX))

    def _get_fernet(self) -> Fernet:
        """为本地密钥文件创建或复用 Fernet 实例。"""

        if self._fernet is None:
            self._fernet = Fernet(self._load_or_create_key())
        return self._fernet

    def _load_or_create_key(self) -> bytes:
        """读取已保存密钥，或生成新的本地密钥文件。"""

        if self.key_path.exists():
            return self.key_path.read_bytes().strip()

        key: bytes = Fernet.generate_key()
        self.key_path.parent.mkdir(parents=True, exist_ok=True)
        self.key_path.write_bytes(key)
        self._best_effort_harden_permissions(self.key_path)
        return key

    def _best_effort_harden_permissions(self, path: Path) -> None:
        """在平台支持时尽量收紧密钥文件权限。"""

        try:
            os.chmod(path, 0o600)
        except OSError:
            return
