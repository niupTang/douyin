import os
import sys


PROJECT_NAME = "Big_Title_Opening_Draft"
VIDEO_PATH = (
    "D:/77053/下载/xwechat_files/wxid_zdea5bir0cpw12_898d/temp/RWTemp/"
    "2026-08/7f918b993972de42d1e1e71dcf87808d/"
    "bd452d07474c9a1dd64b0ca2f68b8752.mp4"
)
AUDIO_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "generated_assets",
    "big_title_opening_audio.mp3",
)
TITLE_TEXT = "一个闭环\n六个动作"

WORKSPACE = os.path.dirname(os.path.abspath(__file__))
SKILL_ROOT = os.path.join(WORKSPACE, "skills", "jianying-editor")
VENDOR_PATH = os.path.join(SKILL_ROOT, "scripts", "vendor")

if VENDOR_PATH not in sys.path:
    sys.path.insert(0, VENDOR_PATH)

import pyJianYingDraft as draft


def default_drafts_root() -> str:
    local_app_data = os.environ.get("LOCALAPPDATA")
    if not local_app_data:
        raise RuntimeError("LOCALAPPDATA is not set; cannot locate Jianying draft root.")

    candidates = [
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

    for path in candidates:
        if os.path.exists(path):
            return path

    os.makedirs(candidates[0], exist_ok=True)
    return candidates[0]


def main() -> None:
    if not os.path.exists(VIDEO_PATH):
        raise FileNotFoundError(VIDEO_PATH)
    if not os.path.exists(AUDIO_PATH):
        raise FileNotFoundError(AUDIO_PATH)

    drafts_root = default_drafts_root()
    folder = draft.DraftFolder(drafts_root)
    script = folder.create_draft(
        PROJECT_NAME,
        width=544,
        height=720,
        fps=30,
        allow_replace=True,
    )

    video_material = draft.VideoMaterial(VIDEO_PATH)
    audio_material = draft.AudioMaterial(AUDIO_PATH)
    duration = video_material.duration

    script.add_track(draft.TrackType.video, "Main Video")
    script.add_track(draft.TrackType.audio, "Original Audio")
    script.add_track(draft.TrackType.text, "Opening Title")

    script.add_segment(
        draft.VideoSegment(video_material, draft.Timerange(0, duration)),
        "Main Video",
    )
    script.add_segment(
        draft.AudioSegment(audio_material, draft.Timerange(0, duration), volume=1.0),
        "Original Audio",
    )
    script.add_segment(
        draft.TextSegment(
            TITLE_TEXT,
            draft.Timerange(0, draft.tim("3s")),
            style=draft.TextStyle(
                size=18.0,
                bold=True,
                color=(1.0, 0.94, 0.18),
                align=1,
                line_spacing=-8,
                auto_wrapping=True,
                max_line_width=0.92,
            ),
            border=draft.TextBorder(alpha=1.0, color=(0.02, 0.02, 0.02), width=55.0),
            background=draft.TextBackground(
                color="#000000",
                alpha=0.38,
                width=0.92,
                height=0.42,
                round_radius=0.08,
                horizontal_offset=0.5,
                vertical_offset=0.48,
            ),
            clip_settings=draft.ClipSettings(transform_y=0.08),
        ),
        "Opening Title",
    )

    script.save()

    draft_dir = os.path.join(drafts_root, PROJECT_NAME)
    print(f"Draft created: {PROJECT_NAME}")
    print(f"Draft path: {draft_dir}")
    print(f"Duration seconds: {duration / 1_000_000:.2f}")


if __name__ == "__main__":
    main()
