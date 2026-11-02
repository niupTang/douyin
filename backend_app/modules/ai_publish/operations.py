from backend_app.modules.accounts import repository as account_repository
from myUtils.postVideo import post_video_tencent, post_video_DouYin, post_video_ks, post_video_xhs

from . import repository as publish_repository
from .service import publish_video as publish_video_service


def create_publish_operation(get_db_path):

    def save_publish_record(platform_type, title, tags, file_list, account_list, status, error_message=None,
                              views=0, likes=0, comments=0, shares=0, video_url=None):
        return publish_repository.save_record(
            get_db_path(),
            platform_type,
            title,
            tags,
            file_list,
            account_list,
            status,
            error_message,
            views,
            likes,
            comments,
            shares,
            video_url,
        )


    def validate_account_files_for_platform(platform_type, account_list):
        return account_repository.validate_account_files_for_platform(
            get_db_path(),
            platform_type,
            account_list,
        )


    def publish_video_payload(payload):
        return publish_video_service(
            payload,
            validate_accounts=validate_account_files_for_platform,
            publishers={
                1: post_video_xhs,
                2: post_video_tencent,
                3: post_video_DouYin,
                4: post_video_ks,
            },
            save_record=save_publish_record,
        )

    return publish_video_payload
