---
name: Video conversion queue
about: Upload a video for the free GitHub queue worker
title: "[queue] "
---

Use this template for one video job.

1. Keep the queue block below.
2. Leave `source=attachment` if you drag a video into the issue body.
3. Replace `source=` with a public direct URL if you already have one.
4. On the free GitHub plan, issue-uploaded videos are limited to 10 MB.

```queue
source=attachment
model=Small (fastest, ~99 MB)
resolution=Original
invert=false
smoothing=60
preserve_audio=true
```

Attach exactly one small MP4 or MOV to the issue body, or use a public HTTPS URL for larger videos.
The automation will pick the first attachment link and put the result in the workflow artifact.
