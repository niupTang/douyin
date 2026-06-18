# AI Video Edit Center V1 Design

## Goal

Upgrade the current basic video edit form into an AI video editing workspace that matches the provided reference layout: material/task sidebar, central player and timeline, AI assistant panel, and a clear upload-to-publish workflow.

## Scope

V1 focuses on product experience and a runnable workflow:

- Keep the existing backend `/video/talkingEdit` and `/video/tasks` endpoints.
- Replace the single-form UI with a three-column editing workspace.
- Show AI-style analysis panels with deterministic recommendations derived from the selected material and form values.
- Make "one-click generate edit version" call the existing FFmpeg talking-head edit endpoint.
- Preserve generated outputs in the material library through the current backend behavior.

## UI Structure

- Top workflow bar: Upload Material, Content Recognition, Smart Edit, Subtitles/Cover, Export/Publish.
- Left panel: New task action, material cards, asset counters, history task cards.
- Center panel: file title, aspect ratio controls, player, playback controls, multi-track timeline, edit toolbar, output stats.
- Right panel: AI assistant tabs, video summary, key points, recommended clips, one-click generation.

## Data Flow

1. Load materials from `/getFiles`.
2. Load edit tasks from `/video/tasks`.
3. Select the first available video by default.
4. User adjusts aspect ratio/title/output name or accepts defaults.
5. User clicks one-click generation.
6. Frontend posts to `/video/talkingEdit`.
7. On success, refresh materials and tasks and open the generated output preview.

## Deferred Integrations

- Real ASR transcript extraction.
- Duplicate/filler removal based on transcript timestamps.
- Remotion animation cards and popups.
- Cover image generation.
- One-click publish handoff to publish center.
