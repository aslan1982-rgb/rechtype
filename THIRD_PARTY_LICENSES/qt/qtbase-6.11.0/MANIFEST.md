# QtBase 6.11.0 license manifest

This directory contains the license and attribution material for the six Qt
runtime files shipped by RechType 0.0.2:

| Packaged file | Size (bytes) | SHA-256 |
|---|---:|---|
| `bin/Qt6Core.dll` | 10,486,584 | `37FDE8EBD11B474B806A1CF8D4564780DC51AFDAD3AC3611CD0AA92982F73687` |
| `bin/Qt6Gui.dll` | 9,544,504 | `96B445DD611F30A3E3B938D981C2B13009D65294F48A8AC5F53DDE8037132B53` |
| `bin/Qt6Network.dll` | 1,770,808 | `7570AA0A43028912112AB1569F3349E60942A29944C4EEB48F3B7346D168782B` |
| `bin/Qt6Widgets.dll` | 6,588,216 | `48DEB69896F3185C8FE21221262670591DDC0CE9E7F2182BE682E9F28208F7A3` |
| `plugins/platforms/qwindows.dll` | 1,000,248 | `A6076030A5F0BF1B9254B0999E5260F66B1ABD3B51214777E47A7C2E1D7CAD81` |
| `bin/opengl32sw.dll` | 20,639,888 | `B04DE4541863BC7D8879040A78889C4849C1B1DA2784C4630F734C146C2998CE` |

The first five files report product version `6.11.0.0`. Their notices were
copied without modification from the QtBase `v6.11.0` source archive. The
archive used for this audit has SHA-256
`92C107E3340661DA5FCA50739F83669216914C21AE43519296267B63F0B97A81`.
The source archive itself and all Qt source code are intentionally excluded
from this distributable directory.

## Directory layout

- `LICENSES/` contains the Qt LGPL v3 text (and the incorporated GPL v3 text)
  plus only the SPDX license texts needed by the selected attributions.
- `src/` and `util/` preserve the QtBase source-relative paths of every
  selected `qt_attribution.json` and every non-empty `LicenseFile` referenced
  by it. No implementation source files are included.
- `opengl32sw/` covers the separately supplied software OpenGL fallback.

## Selected QtBase attributions

`Qt6Core.dll`:

- `src/3rdparty/{blake2,double-conversion,easing,md4,md5,pcre2,rfc6234,sha1,sha3,siphash,tinycbor,zlib}`
- `src/corelib/global`
- `src/corelib/mimetypes/3rdparty`
- `src/corelib/text`

`Qt6Gui.dll` and the Windows platform path used by `qwindows.dll`:

- `src/3rdparty/{D3D12MemoryAllocator,emoji-segmenter,freetype,harfbuzz-ng,icc,md4c,VulkanMemoryAllocator,wintab}`
- `src/gui/{opengl,painting,rhi,text,vulkan}`
- `util/gradientgen`

`Qt6Network.dll`:

- `src/3rdparty/libpsl`

`Qt6Widgets.dll` has no separate `qt_attribution.json` in QtBase 6.11.0; its
Qt and transitive QtGui/QtCore terms are covered above. Attributions for
platforms and plugins not shipped by RechType (Android, Cocoa, Wayland, XCB,
image-format plugins, and similar build-only material) were not copied.

## `opengl32sw.dll`

Binary strings identify this Qt-provided software renderer as Mesa 11.2.2
llvmpipe with LLVM 3.6.2. The following exact notices are included:

- `Mesa-11.2.2-COPYING.txt` and `Mesa-11.2.2-license.html`, extracted from the
  official Mesa 11.2.2 release archive (SHA-256
  `E2453014CD2CC5337A5180CDEFFE8CF24FFFBB83E20A96888E2B01DF868EAAE6`).
- `LLVM-3.6.2-LICENSE.txt`, from the LLVM `llvmorg-3.6.2` source tag.
- `NOTICE-Qt-Mesa-llvmpipe.html` and `NOTICE-Qt-LLVM.html`, the Qt 6.11
  binary-attribution pages, which also reproduce the Khronos and C11 threads
  notices applicable to Qt's Windows software rasterizer.

Upstream references:

- <https://github.com/qt/qtbase/tree/v6.11.0>
- <https://archive.mesa3d.org/older-versions/11.x/11.2.2/>
- <https://github.com/llvm/llvm-project/tree/llvmorg-3.6.2/llvm>
- <https://doc.qt.io/qt-6/qt-attribution-llvmpipe.html>
- <https://doc.qt.io/qt-6/qt-attribution-llvm.html>
