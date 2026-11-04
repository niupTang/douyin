import os
import sys


PROJECT_NAME = "Codex_Jianying_Test_Draft"
WORKSPACE = os.path.dirname(os.path.abspath(__file__))
SKILL_ROOT = os.path.join(WORKSPACE, "skills", "jianying-editor")
VENDOR_PATH = os.path.join(SKILL_ROOT, "scripts", "vendor")
ASSETS_DIR = os.path.join(SKILL_ROOT, "assets")

if VENDOR_PATH not in sys.path:
    sys.path.insert(0, VENDOR_PATH)

import pyJianYingDraft as draft


def default_drafts_root() -> str:
    local_app_data = os.environ.get("LOCALAPPDATA")
    candidates = []
    if local_app_data:
        candidates.extend(
            [
                os.path.join(
                    local_app_data,
                    "JianyingPro",
                    "User Data",
                    "Projects",
                    "com.lveditor.draft",
                ),
                os.path.join(
                    local_app_data,
                    "CapCut",
                    "User Data",
                    "Projects",
                    "com.lveditor.draft",
                ),
            ]
        )
    for path in candidates:
        if os.path.exists(path):
            return path
    if candidates:
        os.makedirs(candidates[0], exist_ok=True)
        return candidates[0]
    raise RuntimeError("LOCALAPPDATA is not set; cannot locate Jianying draft root.")


def main() -> None:
    drafts_root = default_drafts_root()
    video_path = os.path.join(ASSETS_DIR, "video.mp4")
    audio_path = os.path.join(ASSETS_DIR, "audio.mp3")

    if not os.path.exists(video_path):
        raise FileNotFoundError(video_path)
    if not os.path.exists(audio_path):
        raise FileNotFoundError(audio_path)

    folder = draft.DraftFolder(drafts_root)
    script = folder.create_draft(
        PROJECT_NAME,
        width=1920,
        height=1080,
        fps=30,
        allow_replace=True,
    )

    script.add_track(draft.TrackType.video, "Main Video")
    script.add_track(draft.TrackType.audio, "BGM")
    script.add_track(draft.TrackType.text, "Titles")

    duration = draft.tim("5s")
    script.add_segment(
        draft.VideoSegment(video_path, draft.Timerange(0, duration)),
        "Main Video",
    )
    script.add_segment(
        draft.AudioSegment(audio_path, draft.Timerange(0, duration), volume=0.45),
        "BGM",
    )
    script.add_segment(
        draft.TextSegment(
            "Codex Jianying Test Draft",
            draft.Timerange(draft.tim("0.6s"), draft.tim("2.4s")),
            style=draft.TextStyle(size=9.0, bold=True, color=(1.0, 1.0, 1.0)),
            clip_settings=draft.ClipSettings(transform_y=0.62),
        ),
        "Titles",
    )
    script.add_segment(
        draft.TextSegment(
            "自动生成草稿成功",
            draft.Timerange(draft.tim("3s"), draft.tim("2s")),
            style=draft.TextStyle(size=7.0, color=(0.9, 0.95, 1.0)),
            clip_settings=draft.ClipSettings(transform_y=-0.72),
        ),
        "Titles",
    )

    script.save()
    draft_dir = os.path.join(drafts_root, PROJECT_NAME)
    print(f"Draft created: {PROJECT_NAME}")
    print(f"Draft path: {draft_dir}")
    print(f"Content exists: {os.path.exists(os.path.join(draft_dir, 'draft_content.json'))}")


if __name__ == "__main__":
    main()
