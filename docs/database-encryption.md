# 本地数据库加密

数据库使用 SQLCipher 4 加密，业务连接统一经 backend_app.common.sqlite。
原有未配置加密的测试库仍可作为普通 SQLite 数据库使用；存在 .cipher.json 时必须从系统凭据库取得正确密码。
遇到已加密但缺少配置或凭据的文件会拒绝打开，不会覆盖或降级成明文。

主数据库仍为 E:\social-auto-upload\db\database.db。
相邻 database.db.cipher.json 只包含算法、版本和系统凭据引用，不含密码。
密码存放在当前 Windows 用户的凭据管理器中，服务名为 Sunbird OS Database，不写入源码。

## 迁移与恢复

先退出 Sunbird OS 并确认没有数据库使用进程。使用项目虚拟环境运行：

```powershell
E:\social-auto-upload\.venv\Scripts\python.exe E:\social-auto-upload\scripts\encrypt_database.py
```

脚本交互式读取密码。也可由受控启动环境提供 SAU_DATABASE_PASSWORD，避免将密码作为命令行参数。
迁移前导出加密副本，检查表结构、索引、触发器、每表行数和完整性，生成同样加密的备份后再替换原库。
备份位于 db/backups，配套保存 .cipher.json；目录已加入 .gitignore。
迁移失败且尚未替换原文件时，原数据库继续保留。

迁移到另一台电脑或 Windows 用户时，需要数据库原密码重新建立系统凭据。
同一脚本能验证已经加密的文件并重新保存凭据配置，不会把数据重新初始化。
若要恢复备份，先停止应用，将加密备份和配套元数据恢复到目标路径，并校验当前用户凭据。

数据库加密保护的是磁盘文件；程序在当前 Windows 用户下运行时仍可正常读取和导出。
Cookie 文件、媒体文件和旧备份不因为数据库迁移而自动加密。
后续生成桌面安装包前需要重新安装 requirements.txt 并重新构建后端，构建脚本已包含 sqlcipher3。
