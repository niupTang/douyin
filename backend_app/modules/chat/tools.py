from backend_app.common.database import connect


# Explicit columns keep credentials, raw payloads and account file paths out of model input.
QUERIES = {
    'accounts': 'SELECT id,type,userName AS name,status,follower_count FROM user_info',
    'benchmark_accounts': '''SELECT id,nickname,homepage_url,status,last_sync_at,
        followers_count,video_count FROM douyin_benchmark_accounts''',
    'materials': 'SELECT id,filename,filesize,upload_time FROM file_records',
    'publish_records': '''SELECT id,platform_type,title,status,error_message,
        views,likes,comments,shares,video_url,created_at FROM publish_records''',
}


def register_chat_tools(registry, db_path):
    def get_video_links(video_ids, source='benchmark'):
        tables = {'benchmark': 'douyin_benchmark_videos', 'own': 'douyin_own_videos',
                  'publish': 'publish_records'}
        placeholders = ','.join('?' for _ in video_ids)
        with connect(db_path) as conn:
            rows = conn.execute(
                f'SELECT id,title,video_url FROM {tables[source]} WHERE id IN ({placeholders})',
                video_ids,
            ).fetchall()
        by_id = {row['id']: dict(row) for row in rows}
        return {'source': source, 'items': [by_id[vid] for vid in video_ids if vid in by_id],
                'missing_ids': [vid for vid in video_ids if vid not in by_id]}

    def query_workbench_data(entity, limit=30):
        with connect(db_path) as conn:
            rows = conn.execute(QUERIES[entity] + ' ORDER BY id DESC LIMIT ?', (limit,)).fetchall()
        return {'entity': entity, 'items': [dict(row) for row in rows], 'limit': limit}

    def sync_benchmark_account(account_id, max_videos=20):
        with connect(db_path) as conn:
            row = conn.execute('SELECT homepage_url FROM douyin_benchmark_accounts WHERE id=?',
                               (account_id,)).fetchone()
        if not row:
            raise ValueError('对标账号不存在')
        return registry.gateway.execute('collect_douyin_account', {
            'homepage_url': row['homepage_url'], 'max_videos': max_videos,
        })

    registry.register('get_video_links', '按本地作品记录 ID 查询真实标题和 video_url。展示作品时用 [标题](video_url)，不能拿本地 ID 拼抖音网址。空链接表示未采集。', {
        'type': 'object', 'required': ['video_ids'], 'properties': {
            'video_ids': {'type': 'array', 'minItems': 1, 'maxItems': 50, 'uniqueItems': True,
                          'items': {'type': 'integer', 'minimum': 1}},
            'source': {'type': 'string', 'enum': ['benchmark', 'own', 'publish']},
        },
    }, get_video_links)
    registry.register('query_workbench_data', '查询本地账号、对标账号、素材或发布记录，返回真实数据及 ID；发布记录有 video_url 时展示为可点击链接。', {
        'type': 'object', 'required': ['entity'], 'properties': {
            'entity': {'type': 'string', 'enum': list(QUERIES)},
            'limit': {'type': 'integer', 'minimum': 1, 'maximum': 100},
        },
    }, query_workbench_data)
    registry.register('sync_benchmark_account', '根据本地对标账号 ID 同步资料和近期作品，等待真实结果。', {
        'type': 'object', 'required': ['account_id'], 'properties': {
            'account_id': {'type': 'integer', 'minimum': 1},
            'max_videos': {'type': 'integer', 'minimum': 1, 'maximum': 50},
        },
    }, sync_benchmark_account, side_effect=True, effect_type='collect', entitlement='benchmarkCollect')
