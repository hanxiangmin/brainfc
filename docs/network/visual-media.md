# Rotating hero / 旋转主图

The README animation and website video use actual frames from the local viewer.
Hyperedge **H06** and its six members stay selected while the camera completes
one orbit. The brain, ROI coordinates, membership links and labels are rendered
by the application. The input is the same synthetic AAL SPM12 / 116 ROI fixture
used by the screenshot gallery; it is not a patient scan or an inferred biological system.

README 动图和网站视频来自实际本地查看器。相机环绕一周时，**H06** 超边及其六个
成员持续高亮。脑表面、脑区坐标、成员连线和标签均由应用渲染。输入与截图图集
相同，为 AAL SPM12 / 116 ROI 合成示例，不代表患者扫描或生物学结论。

| Asset | Purpose | Format |
|---|---|---|
| `website/public/media/hyperedge-orbit.gif` | English and Chinese README | Original 1600 × 1000, 5.04 s loop |
| `website/public/media/hyperedge-orbit.mp4` | English and Chinese website hero | 1044 × 728, silent H.264, 5.04 s loop |
| `website/public/media/manifest.json` | Provenance | Input hash, member IDs, frame hashes and encoded asset hashes |

The website offers play/pause and respects `prefers-reduced-motion` at load and
when the setting changes. The README picture supplies a still image for reduced
motion. The static `gallery/hero.png` remains the social-preview image.
The README image has no fixed HTML width or height: GitHub can fit it to the
content column while preserving its native 8:5 aspect ratio.

网站支持播放、暂停，并在加载和设置变化时响应减少动态效果偏好。README 为该
偏好提供静态图；社交分享预览继续使用 `gallery/hero.png`。
README 主图保留原始 1600 × 1000 像素，不设置固定显示宽高，适应页面时保持 8:5 比例。

## Reproduce / 复现

Use the synthetic fixtures from [prepare_gallery.py](https://github.com/hanxiangmin/Hyper-Brain/blob/ded30680e600ecbe79c2ef67a1ffaae02e3d7c33/docs/../examples/prepare_gallery.py)
with the local server and installed atlas resources. The capture script requires
Node.js, Playwright and Chromium. Encoding requires Python, Pillow and FFmpeg.
These are documentation-generation tools, not application runtime dependencies.

```bash
python examples/prepare_gallery.py --url http://127.0.0.1:8765
node frontend/scripts/capture-orbit.cjs
python website/scripts/build-orbit.py --captures .work/orbit-frames --ffmpeg ffmpeg
```

Set `HYPERBRAIN_URL` for a different local server. Captures stay under `.work` and
are not published as source data. The encoder excludes duplicate revolution
endpoints. It retains the complete workbench at source resolution for the README and crops the scene
for the website; it does not generate intermediate geometry or alter data values.
Use `--readme-only` to rebuild the GIF without re-encoding the existing website video.
