# GitHub Free Queue Setup

1. Push this repo to GitHub.
2. In repo settings, enable GitHub Pages and choose GitHub Actions as the source.
3. Open the published Pages URL.
4. Create an issue from the Video conversion queue template.
5. Attach one small MP4 or MOV, or set `source=` to a public HTTPS video URL.

What the flow does:

- GitHub Pages serves `docs/index.html`.
- GitHub Actions processes one issue at a time.
- The result is uploaded as a workflow artifact for 7 days.

Hard limits:

- This is still a free queue, so it is not fast under load.
- Only Small and Base are enabled.
- Public source URLs must be HTTPS and public.
- Free-plan issue uploads for videos are limited to 10 MB.
