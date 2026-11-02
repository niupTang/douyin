# 抖音内容搜索采集与对标作品池设计

## 1. 目标

用户输入关键词后，系统通过抖音综合搜索自动采集几十条内容，展示标题/文案、获赞数、封面、作者和作品链接，并支持批量加入对标作品池。

内容搜索结果不要求先绑定作者账号。作品可以独立存在；如果后续能够从作品详情页补采作者信息，再自动关联已有账号。

## 2. 关键决策

- 搜索结果保持抖音综合排序，不按获赞数二次排序。
- 默认采集 50 条，允许配置 10–100 条。
- 视频和图文都采集，并标注作品类型。
- 继续使用后台 Playwright 批量采集。
- 登录失效、验证码或风控时暂停任务，使用可见浏览器人工处理后继续。
- 不创建“未知作者”虚拟账号。
- 作品与作者弱绑定：`account_id` 允许为空。
- 现有账号同步功能继续保留。

## 3. 数据模型

新增 `douyin_content_search_tasks`：

- `id`
- `keyword`
- `target_count`
- `status`：`pending`、`running`、`paused`、`success`、`failed`、`stopped`
- `collected_count`
- `error_message`
- `started_at`
- `finished_at`
- `created_at`
- `updated_at`

扩展 `douyin_benchmark_videos`：

- 将 `account_id` 改为可空
- `source_type`：`account_sync`、`content_search`、`manual_import`
- `source_keyword`
- `search_task_id`
- `source_rank`
- `author_name`
- `author_url`
- `author_sec_uid`
- `video_type`：`video`、`note`
- `like_count_value`：用于后续数值筛选，保留原始 `like_count` 用于展示

现有账号同步作品默认 `source_type=account_sync`；旧数据保持原有 `account_id` 不变。

作品唯一性优先使用抖音作品 URL 规范化后的值；同一作品被多个关键词搜到时复用作品记录，并记录搜索来源关联，避免重复入库。

## 4. 采集流程

1. 前端提交关键词和目标数量，后端创建搜索任务并立即返回任务 ID。
2. 后台 Playwright 打开抖音内容搜索页，使用综合排序。
3. 通过滚动触发结果加载，解析作品链接、标题/文案、封面、作者、获赞数、作品类型和原始排名。
4. 规范化作品链接并去重。
5. 将结果逐批写入数据库，前端轮询任务状态，实时显示新增结果。
6. 达到目标数量，或连续多轮没有新内容后结束任务。
7. 如果登录失效或出现验证，任务状态置为 `paused`；用户在可见浏览器中完成处理后继续。
8. 作品详情页可作为后续补采入口，用于补齐作者信息，不影响作品先进入作品池。

## 5. 接口

```text
POST /benchmark/douyin/content-search
GET  /benchmark/douyin/content-search/{task_id}
POST /benchmark/douyin/content-search/{task_id}/stop
GET  /benchmark/douyin/content-search/{task_id}/results
POST /benchmark/douyin/content-search/results/import
GET  /benchmark/douyin/videos
POST /benchmark/douyin/videos/{video_id}/resolve-author
```

搜索接口为异步接口。结果接口支持按任务、关键词、来源类型和是否已加入作品池筛选。

批量导入作品池时，已有作品只更新来源关联，不重复创建；作品拆解继续复用现有视频分析接口。

## 6. 页面设计

“抖音对标管理”增加三个视图：

- 内容搜索：输入关键词、数量，启动/停止任务，实时查看搜索结果。
- 对标作品池：不依赖作者，展示所有已导入作品，支持关键词、来源、作品类型筛选。
- 对标账号：保留原有主页添加、账号同步和按账号查看作品功能。

内容搜索结果按抖音原始排名展示。每条结果展示封面、标题/文案、作者昵称（未知时显示“未知作者”）、获赞数、视频/图文标签、原作品链接和加入状态。

## 7. 兼容性与异常处理

- SQLite 通过启动时幂等迁移增加字段和索引。
- 旧账号作品不迁移、不改归属。
- 账号删除只删除该账号关联的账号同步作品；内容搜索独立作品不受影响。若未来允许账号同步作品被多个来源引用，删除时只清理账号关联，不删除作品实体。
- 解析不到标题的结果丢弃；解析不到作者的结果保留。
- 获赞数保留页面原始文本，同时尽力转换为整数；转换失败不影响展示。
- 抖音 DOM 结构变化时，任务记录失败原因，并保留已采集结果。
- 任务支持停止，停止后已采集结果保留。

## 8. 测试范围

- 作品 URL 规范化和去重。
- “1.2万”“3,456”等获赞数解析。
- 无作者信息的作品可正常入库和展示。
- 旧账号同步作品查询行为不变。
- 内容搜索任务状态流转、停止和失败后结果保留。
- 批量导入不产生重复作品。
- 前端按综合排序显示，不进行获赞数排序。

## 9. 范围控制

第一版只实现内容搜索、结果展示、批量加入作品池和现有作品拆解复用。下载视频、转写、评论采集、语义相似度排序和自动补采作者信息作为后续增强能力。
