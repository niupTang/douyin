async def refresh_valid_accounts(db_path, *, check_cookie, log=None):
    from . import repository

    rows = repository.list_accounts_raw(db_path)
    if log:
        log("\n[INFO] 当前数据表内容：")
        for row in rows:
            log(row)
    refreshed = [list(row) for row in rows]
    for row in refreshed:
        is_valid = await check_cookie(row[1], row[2])
        if not is_valid:
            row[4] = 0
            repository.mark_account_invalid(db_path, row[0])
            if log:
                log("[OK] 用户状态已更新")
    if log:
        for row in rows:
            log(row)
    return refreshed
