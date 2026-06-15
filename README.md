# 太阳鸟自媒体自动化运营系统

这是太阳鸟基于开源项目 `social-auto-upload` 做的二次开发版本，目标是把多平台内容发布、素材管理、发布记录、对标账号分析和 AI 内容生产流程整合到一个本地化运营系统里。

原项目提供了 `抖音`、`Bilibili`、`小红书`、`快手`、`视频号`、`百家号` 以及 `TikTok` 等平台的视频上传、定时发布能力。本版本在此基础上继续增强了后台管理、抖音对标账号同步、作品数据沉淀、作品内容拆解、发布记录追踪和视频处理工作流能力。

这个项目适合内容创作者、自媒体运营者、个人 IP 团队和希望用 AI 提升内容生产效率的人使用。它不是单纯的上传工具，而是一个可以持续沉淀账号、素材、对标作品和内容方法论的本地运营中台。

<img src="media/show/tkupload.gif" alt="tiktok show" width="800"/>

## 目录

- [💡 功能特性](#💡功能特性)
- [🌞 太阳鸟二次开发能力](#🌞太阳鸟二次开发能力)
- [🚀 支持的平台](#🚀支持的平台)
- [💾 安装指南](#💾安装指南)
- [🏁 快速开始](#🏁快速开始)
- [🐇 项目背景](#🐇项目背景)
- [📃 详细文档](#📃详细文档)
- [🐾 交流与支持](#🐾交流与支持)
- [🤝 贡献指南](#🤝贡献指南)
- [📜 许可证](#📜许可证)
- [⭐ Star History](#⭐Star-History)

## 🌞太阳鸟二次开发能力

本版本基于原 `social-auto-upload` 项目继续开发，重点增强了以下能力：

-   **抖音对标账号管理**：输入对标账号主页链接后，自动同步账号昵称、头像、关注数、粉丝数、获赞数、作品数和最近作品。
-   **最新作品同步**：点击同步时，自动扫描并补充最多 20 条本地未同步作品；已有作品会更新标题、封面、点赞数和原始数据。
-   **作品数据沉淀**：保存作品标题/文案、点赞数、作品链接、封面和同步时间，形成自己的对标作品库。
-   **作品内容拆解**：基于已同步的标题和文案，生成开头钩子、核心观点、内容结构、爆点分析、人群痛点、可复刻点和脚本建议。
-   **发布记录追踪**：每次发布都会记录平台、标题、素材、账号、状态和错误信息，方便复盘和排查问题。
-   **素材管理增强**：支持素材上传、列表管理、复制链接、删除素材，并与发布中心联动。
-   **口播剪辑基础能力**：保留 FFmpeg 本地剪辑流程，为后续接入 Remotion、OpenCut、封面生成和 AI 视频工作流预留接口。
-   **Playwright 浏览器缓存迁移**：将 Playwright 浏览器运行依赖迁移到 E 盘，减少 C 盘占用并提升本地部署稳定性。

简单说，这个版本想解决的是：从“发视频”升级到“找对标、拆内容、管素材、做发布、看结果”的完整内容运营流程。

## 💡功能特性

### 已支持平台

-   **国内平台**:
    -   [x] 抖音
    -   [x] 视频号
    -   [x] Bilibili
    -   [x] 小红书
    -   [x] 快手
    -   [x] 百家号
-   **国外平台**:
    -   [x] TikTok

### 核心功能

-   [x] 定时上传 (Cron Job / Scheduled Upload)
-   [ ] Cookie 管理 (部分实现，持续优化中)
-   [ ] 国外平台 Proxy 设置 (部分实现)

### 计划支持与开发中

-   **平台扩展**:
    -   [ ] QQ视频
    -   [ ] YouTube
-   **功能增强**:
    -   [x] 更易用的版本 (GUI / CLI 交互优化)
    -   [x] API 封装
    -   [ ] Docker 部署
    -   [ ] 自动化上传 (更智能的调度策略)
    -   [ ] 多线程/异步上传优化
    -   [ ] Slack/消息推送通知

---

## 🚀支持的平台

本项目通过各平台对应的 `uploader` 模块实现视频上传功能。您可以在 `examples` 目录下找到各个平台的使用示例脚本。

每个示例脚本展示了如何配置和调用相应的 uploader。

## 💾安装指南

1.  **克隆项目**:
    ```bash
    git clone https://github.com/niupTang/douyin.git
    cd douyin
    ```

2.  **安装依赖**:
    建议在虚拟环境中安装依赖。
    ```bash
    conda create -n social-auto-upload python=3.10
    conda activate social-auto-upload
    # 挂载清华镜像 or 命令行代理
    pip install -r requirements.txt
    ```

3.  **安装 Playwright 浏览器驱动**:
    ```bash
    playwright install chromium firefox
    ```
    根据您的需求，至少需要安装 `chromium`。`firefox` 主要用于 TikTok 上传（旧版）。

4.  **修改配置文件**:
    复制 `conf.example.py` 并重命名为 `conf.py`。
    在 `conf.py` 中，您需要配置以下内容：
    -   `LOCAL_CHROME_PATH`: 本地 Chrome 浏览器的路径，比如 `C:\Program Files\Google\Chrome\Application\chrome.exe` 保存。
    
    **临时解决方案**

    需要在根目录创建 `cookiesFile` 和 `videoFile` 两个文件夹，分别是 存储cookie文件 和 存储上传文件 的文件夹

5.  **配置数据库**:
    如果 db/database.db 文件不存在，您可以运行以下命令来初始化数据库：
    ```bash
    cd db
    python createTable.py
    ```
    此命令将初始化 SQLite 数据库。

6.  **启动后端项目**:
    ```bash
    python sau_backend.py
    ```
    后端项目将在 `http://localhost:5409` 启动。

7.  **启动前端项目**:
    ```bash
    cd sau_frontend
    npm install
    npm run dev
    ```
    前端项目将在 `http://localhost:5173` 启动，在浏览器中打开此链接即可访问。


> 非程序员用户可以参考：[新手级教程](https://juejin.cn/post/7372114027840208911)


## 🏁快速开始

1.  **准备 Cookie**: 
    大多数平台需要登录后的 Cookie 信息才能进行操作。请参照 examples 目录下各 `get_xxx_cookie.py` 脚本（例如 get_douyin_cookie.py, get_ks_cookie.py）的说明，运行脚本以生成并保存 Cookie 文件（通常在 `cookies/[PLATFORM]_uploader/account.json`）。

2.  **准备视频文件**: 
    将需要上传的视频文件（通常为 `.mp4` 格式）放置在 videos 目录下。
    部分平台支持视频封面，可以将封面图片（例如 `.png` 格式，与视频同名）也放在此目录。
    如果需要上传标题及标签，请在视频文件旁边创建一个同名的 `.txt` 文件，内容为标题和标签，以换行分隔。

3.  **修改并运行示例脚本**:
    打开 examples 目录中您想使用的平台的上传脚本（例如 upload_video_to_douyin.py）。
    -   根据脚本内的注释和说明，确认 Cookie 文件路径、视频文件路径等配置是否正确。
    -   您可以修改脚本以适应您的具体需求，例如批量上传、自定义标题、标签等。

4.  **执行上传**:
    运行修改后的示例脚本，例如：
    ```bash
    python examples/upload_video_to_douyin.py
    ```

## 🐇项目背景

本仓库是太阳鸟基于 `social-auto-upload` 做的二次开发版本。原项目最初用于自动化管理社交媒体视频发布，本版本继续围绕自媒体运营场景扩展，把发布、素材、数据、对标账号和 AI 内容拆解整合到同一个本地系统中。

如果您需要搭建自己的内容运营系统，可以基于这个版本继续扩展，比如接入更多平台、增加评论分析、自动生成选题、自动剪辑视频、自动生成封面和自动发布。

## 📃详细文档

更详细的文档和说明，请查看：[social-auto-upload 官方文档](https://sap-doc.nasdaddy.com/)

## 🐾交流与支持

[☕ Donate as u like](https://www.buymeacoffee.com/hysn2001m) - 如果您觉得这个项目对您有帮助，可以考虑赞助。

如果您也是独立开发者、技术爱好者，对 #技术变现 #AI创业 #跨境电商 #自动化工具 #视频创作 等话题感兴趣，欢迎加入社群交流。

### Creator

<table>
    <td align="center">
        <a href="https://sap-doc.nasdaddy.com/">
            <img src="media/mp.jpg" width="200px" alt="NasDaddy公众号"/>
            <br />
            <sub><b>微信公众号</b></sub>
        </a>
        <br />
        <a href="https://github.com/dreammis/social-auto-upload/commits?author=dreammis" title="Code">💻</a>
        <br />
        关注公众号，后台回复 `上传` 获取加群方式
    </td>
    <td align="center">
        <a href="https://sap-doc.nasdaddy.com/">
            <img src="media/QR.png" width="200px" alt="赞赏码/入群引导"/>
            <br />
            <sub><b>交流群 (通过公众号获取)</b></sub>
        </a>
        <br />
        <a href="https://sap-doc.nasdaddy.com/" title="Documentation">📖</a>
        <br />
        如果您觉得项目有用，可以考虑打赏支持一下
    </td>
</table>

### Active Core Team

<table>
    <td align="center">
        <a href="https://leedebug.github.io/">
            <img src="media/edan-qrcode.png" width="200px" alt="Edan Lee"/>
            <br />
            <sub><b>Edan Lee</b></sub>
        </a>
        <br />
        <a href="https://github.com/dreammis/social-auto-upload/commits?author=LeeDebug" title="Code">💻</a>
        <a href="https://leedebug.github.io/" title="Documentation">📖</a>
        <br />
        封装了 api 接口和 web 前端管理界面
        <br />
        （请注明来意：进群、学习、企业咨询等）
    </td>
</table>

## 🤝贡献指南

欢迎各种形式的贡献，包括但不限于：

-   提交 Bug报告 和 Feature请求。
-   改进代码、文档。
-   分享使用经验和教程。

如果您希望贡献代码，请遵循以下步骤：

1.  Fork 本仓库。
2.  创建一个新的分支 (`git checkout -b feature/YourFeature` 或 `bugfix/YourBugfix`)。
3.  提交您的更改 (`git commit -m 'Add some feature'`)。
4.  Push到您的分支 (`git push origin feature/YourFeature`)。
5.  创建一个 Pull Request。

## 📜许可证

本项目暂时采用 [MIT License](LICENSE) 开源许可证。

## ⭐Star-History

> 如果这个项目对您有帮助，请给一个 ⭐ Star 以表示支持！

[![Star History Chart](https://api.star-history.com/svg?repos=dreammis/social-auto-upload&type=Date)](https://star-history.com/#dreammis/social-auto-upload&Date)
