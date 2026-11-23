# Test A: exact Chrono installation approval plan

5 November 2026 IST. Planning-only approval completed; no solver packages installed. The first read-only version probe failed because the sanitized environment lacked USERPROFILE; the corrected probe used a Jarvis-owned empty profile and reused the same verified binary. Exactly one dependency dry-run then succeeded in 12.062 s. No shared service or configuration changed.

## Concrete requested scope

The official Windows PyChrono 10.0.0/Python 3.12 resolution has **72 archives, 1,913,155,814 bytes**. Full hashes, URLs, exact builds and licenses are retained privately in `app/.jarvis-runtime/discovery/tools/micromamba-2.10.0-0/dry-run.json`. This is development dependency preparation, not autonomous Test A evidence.

Proposed isolated prefix: `app/.venv-discovery-chrono`; owned download/extraction cache under `app/.jarvis-runtime/discovery/tools/chrono-10.0.0/`. Download only exact resolved public official projectchrono/release and conda-forge archive URLs; verify SHA-256 and declared size. Maximum 2.1 GB archive downloads and 14 GB total owned cache/prefix disk, stop on quota or a hash mismatch. No silent re-resolution. Preserve failed attempts.

Inspect archive paths/licenses and reject executable post-link/pre-link scripts before linking. No package scripts, admin, PATH/system/driver install, paid compute, cloud models or shipped Lab activation. NVIDIA CUDA libraries and Intel MKL are bundled **runtime dependencies** in this official build even for intended CPU Chrono::Vehicle use; this grant must explicitly cover their vendor licenses. No GPU simulation, driver change or external hardware actuation. If script-free linking cannot be proven, stop before install and revise the plan.

After license/hash/path checks, link only offline exact packages in the owned prefix without scripts, then permit at most 50 fixed trusted CPU-only import/golden/vehicle invocations, each at most 120 seconds, within existing daily CPU/resource authorization. No generated/downloaded Python scripts on the host; authored workers must be reviewed and fixed. A separate approval is required if isolation or resource constraints cannot be satisfied. Each invocation reserves a non-refundable slot before dispatch. Neither installation nor a golden benchmark passes autonomous A.

## Exact archive manifest

| Package | Version / build | Bytes | Declared license | SHA-256 |
|---|---|---:|---|---|
| cuda-version | 12.8 / h5d125a7_3 | 21086 | LicenseRef-NVIDIA-End-User-License-Agreement | 6f93ceb66267e69728d83cf98673221f6b1f95a3514b3a97777cfd0ef8e24f3f |
| tzdata | 2026e / h5d301ff_0 | 119208 | LicenseRef-Public-Domain | 2b7ca858879f183ce2dcc65b300f48a0133d5430550f35b23d80d405a0788dbf |
| ca-certificates | 2026.10.23 / h4c7d964_0 | 130423 | ISC | f1d280d2618de987204102090e83733089c092dc2dd45686fd3dcbe809034f6a |
| python_abi | 3.12 / 9_cp312 | 6751 | BSD-3-Clause | ee9c2922e07afc85fc82d5fa82c9ac2c79da3be3283a5e17bf2f2ae38dbd02fb |
| cuda-cudart_win-64 | 12.8.90 / he0c23c2_1 | 22914 | LicenseRef-NVIDIA-End-User-License-Agreement | da2356ce91d1105be629eb8b15e7cb8c3ff3f56033c5d9a0ebddc2314d91e71b |
| mpi | 1.0 / openmpi | 4739 | BSD 3-clause | 83cedbffb8d1b01d105cec5e23b2a7f8d2c96a82b77e5a43ff0074e819174a4a |
| ucrt | 10.0.26100.0 / h57928b3_0 | 694692 | LicenseRef-MicrosoftWindowsSDK10 | 3005729dce6f3d3f5ec91dfc49fc75a0095f9cd23bab49efb899657297ac91a5 |
| libwinpthread | 12.0.0.r688.g6b2176247.1 / h57928b3_0 | 34475 | MIT | bab5558663cb0e964988b859abd69d0f2380b6ea9f140495ab543e51af13635d |
| vcomp14 | 14.51.36247 / habf1de7_42 | 155686 | LicenseRef-MicrosoftVisualCpp2015-2022Runtime | b3558ed059d6272ef919ea959311af73c35b5fe43c789cd43f71b398671fec49 |
| vc14_runtime | 14.51.36247 / habf1de7_42 | 767099 | LicenseRef-MicrosoftVisualCpp2015-2022Runtime | 8dfbfd68ebf53249d11e528cbb80ad5a2460b0c5b4636eed82ee0d3950827a3d |
| vc | 14.5 / ha367084_42 | 21309 | BSD-3-Clause | 0598ca1ce913618cff9bd90391bcf75cd9edb22057c85dd6784dd762b7a888e2 |
| libiconv | 1.18 / hc1393d2_3 | 694899 | LGPL-2.1-only | 35e04e3ddac7720fc7c550a1c9f998604299d6a7bd1f3ec9b2825d825061daa2 |
| icu | 78.3 / h5112557_2 | 16835644 | MIT | 75c549b55b673e15de8785a8e5dd85bca7eb612eee0ff4dc8d7bdaa15eacbdbb |
| opencl-headers | 2025.06.13 / h826ebb9_0 | 56082 | Apache-2.0 | 3acfdfe4b914a9fd8c950da6c13cfe563896744709eb5c4c7a926919c3e0b630 |
| libusb | 1.0.30 / h6a83c73_1 | 122711 | LGPL-2.1-or-later | b6a4af4d521c5494b5deffdc846823bf3ee18b4d6cb0dd60b1ff5505f8ff6d13 |
| libvulkan-loader | 1.4.357.0 / h477610d_2 | 288787 | Apache-2.0 | 4b094443126c5fc38d200eb0ea335b67e64d966d7aa737bb3141217a787b0c73 |
| llvm-openmp | 23.1.5 / h49e36cd_0 | 344024 | Apache-2.0 WITH LLVM-exception | f7b5e57c99568c23d97759820b9bb2eeae47dff5ba024ddc9dcdc08780da527d |
| console_bridge | 1.0.2 / h477610d_2 | 25896 | BSD-3-Clause | bc63e5b2fd0f9d297ab995531e65eab3ab7bb11c6a87fa132e27d651a5a07e13 |
| libopenblas | 0.3.34 / pthreads_h952cde7_2 | 4772945 | BSD-3-Clause | 138056f68cf8f92cb1830fe1ed950d70856cc840f5f4b2569f9e849cb109bf7e |
| libjpeg-turbo | 3.2.1 / hfd05255_0 | 990502 | IJG AND BSD-3-Clause AND Zlib | 195be7b2ff1eeff02b31cf366437a38d84560c2f6c4facd56b2969024f50957f |
| yaml | 0.2.5 / h6a83c73_3 | 63944 | MIT | 80ee68c1e7683a35295232ea79bcc87279d31ffeda04a1665efdb43cbd50a309 |
| eigen | 3.4.0 / h5112557_2 | 1170810 | MPL-2.0 | c6a44edf0381f66826cd60ed30b07aa4bc5b9ce5de94d458f0c5457fb1d49dfd |
| glfw | 3.5.1 / hfd05255_0 | 120871 | Zlib | 4433ee569c040b68515e8ad479780660110a3f92c1e3ef5982935e6465345111 |
| urdfdom_headers | 2.1.2 / h49e36cd_0 | 19873 | BSD-3-Clause | abe2760066894ac45d5de6d4201235e47eb64084af4f16f5a150d9ac39381fa7 |
| tinyxml2 | 11.0.0 / h5112557_1 | 76850 | Zlib | aace0c0c0dbcd2b0a028ba06573878d6a852228c70d3031e3c035cf9e066b020 |
| libcurand | 10.3.9.90 / he0c23c2_1 | 46826907 | LicenseRef-NVIDIA-End-User-License-Agreement | 0da92fadd7e484ee892a6117edec850b7ee0abb54470d63b42fedb53242e5f07 |
| libcufft | 11.3.3.83 / he0c23c2_1 | 154601218 | LicenseRef-NVIDIA-End-User-License-Agreement | 083ba1d13f5512dae13fd7e3785336d578bc66f01c88917bbf1f53923339a5e4 |
| libnpp | 12.3.3.100 / he0c23c2_1 | 133438869 | LicenseRef-NVIDIA-End-User-License-Agreement | 0c90fefbac866e6af3d7da96cebb5f3b9209857b0088552806140ee7d48b3ade |
| libnvjpeg | 12.3.5.92 / he0c23c2_1 | 2652299 | LicenseRef-NVIDIA-End-User-License-Agreement | 12f41579c7314be8bc076389973c425ea2b3df1aa2cff23a7bcb2f11d177e58c |
| cuda-cudart | 12.8.90 / he0c23c2_1 | 166455 | LicenseRef-NVIDIA-End-User-License-Agreement | 9ae3f5aa47b6b09fd8991059f63080b2c5759b125609e8b0218f44c1ee540bf6 |
| libnvfatbin | 12.8.90 / he0c23c2_1 | 342701 | LicenseRef-NVIDIA-End-User-License-Agreement | 6b8a5bea472b6f4c2194cfb49f866d49837e61dcb9f9900ac1b82cdd43aa44a4 |
| libnvjitlink | 12.8.93 / he0c23c2_1 | 25594915 | LicenseRef-NVIDIA-End-User-License-Agreement | 4b8937983263f24f73eb8e08cc29cfb7114899bdd10addbb3d94aadc53210421 |
| cuda-nvrtc | 12.8.93 / he0c23c2_1 | 56519607 | LicenseRef-NVIDIA-End-User-License-Agreement | b68487e5e8ef36b51e695ac654a7aa32deaad45a354e98404c52dd61fb740674 |
| bzip2 | 1.0.8 / h0ad9c76_10 | 55919 | bzip2-1.0.6 | 04767466ee9227c9c57ab2c6503e0149177d34111c7418d2f420297acb1eb229 |
| libzlib | 1.3.2 / hfd05255_3 | 58529 | Zlib | 0629c2cc0404d3bb29d6baa7b4ba62da80797015e86de050db81ea5a07050527 |
| libexpat | 2.9.0 / hac47afa_0 | 72983 | MIT | d4a8e5aac8999a90cd71aa6f9f5c40d8594ed2b89cd7f898f997767ecc6cd52d |
| openssl | 3.6.5 / hf411b9b_0 | 9402647 | Apache-2.0 | bc44625e0c6d83f3e02b5f6adc01e0e3ca7001d3d94e24959591a57f5a011b9a |
| libffi | 3.7.0 / h3d046cb_1 | 49992 | MIT | 613e8077c5cca5df7fe84ade7d5050301bee3c6c4c450ffe61d34a349ab4f11c |
| libsqlite | 3.54.1 / hf5d6505_101 | 1333137 | blessing | 1f7ddd7d9383cf6ab6ee5a3a84e07a679a8539edc0ddd05fe476ff08142bf742 |
| liblzma | 5.8.3 / hfd05255_1 | 105809 | 0BSD | d36c4a1e1f80fd08e18a407e03622ff2f34dfdd022da6488ad19603dea19e6d5 |
| tk | 8.6.13 / h967ab96_4 | 3782376 | TCL | f19618a3a82cc483dacf1c70a30367ee7b0c7e71b90f1f80e14feff44fbd3688 |
| libpython | 3.12.16 / hfb4101e_0_cpython | 47258 | Python-2.0 | dd208ae5026d15eb90763f6f41b26c502a52c66f77687fa7a8682b7ef33ffd5c |
| glew | 2.3.0 / hdfd1c44_0 | 544026 | BSD-3-Clause | a582ff0418d9b0bbe13d7f42c363506ebfc026b487569885a5cb01c88e2d8641 |
| khronos-opencl-icd-loader | 2024.10.24 / hfd05255_2 | 47649 | Apache-2.0 | 245bd150a9f0b922dc34f173027631a20f18b009604d827a796d792a79bac178 |
| sdl3 | 3.4.20 / h5112557_0 | 1683554 | Zlib | 3fb8599ac9048b7326c6faab57129896751aa0cbe1e2d5650b8340096df42853 |
| libblas | 3.11.0 / 12_h0adab6e_openblas | 67016 | BSD-3-Clause | e019adbf481a7b84de39b535a9dd4beafcb2afad772a5f34d7bf6b360d90e9ee |
| urdfdom | 5.1.2 / h37f4996_0 | 98588 | BSD-3-Clause | ebae061062c900066b849fcba058f0afb530c65256abe9a3e3477a53460d60c4 |
| libcusparse | 12.5.8.93 / he0c23c2_1 | 168226951 | LicenseRef-NVIDIA-End-User-License-Agreement | 4cb21b413e66f3a9eabd44bbc5333776f05af8f00bc985c92cf769523abae365 |
| libcublas | 12.8.5.5 / hac47afa_0 | 464518487 | LicenseRef-NVIDIA-End-User-License-Agreement | 96cf67798d8e2b2c40f518671e904eb04dbdac6571e0be2a560b61fbebb5dff9 |
| libpng | 1.6.59 / hdc8cecf_0 | 385760 | zlib-acknowledgement | 36050852deae6edc98d7b71489b8d07254e2753c69bd524bf5784927cd1f0b2c |
| libxml2-16 | 2.15.4 / h3cfd58e_1 | 515690 | MIT | 819c4edd7b7bcfa9461aeccb56c0a7e9fa7c251163333e64222c142499822958 |
| python | 3.12.16 / hb12b558_0_cpython | 15868346 | Python-2.0 | c51326f96259254d1f977d131b3bd9a366021f4c96cd3724e9c74ec56fc4983e |
| cuda-opencl | 12.8.90 / he0c23c2_1 | 22137 | LicenseRef-NVIDIA-End-User-License-Agreement | eeaa2f889858870b5999af778576e4218fb683a45caee77959d724b3043def3f |
| sdl2 | 2.32.56 / h5112557_0 | 572101 | Zlib | d17da21386bdbf32bce5daba5142916feb95eed63ef92b285808c765705bbfd2 |
| libcblas | 3.11.0 / 12_h2a8eebe_openblas | 67523 | BSD-3-Clause | b9557316891f401956e2fd643c249550683dd3bfabcf7a331f41ce7d7a5d4cb6 |
| liblapack | 3.11.0 / 12_hd232482_openblas | 79547 | BSD-3-Clause | 2cd61d177472f91a50087c07a44609086fc3aa5f18b7b4c49f3bb487117fa2b9 |
| libcusolver | 11.7.3.90 / he0c23c2_1 | 158340148 | LicenseRef-NVIDIA-End-User-License-Agreement | c967651aab88a4a9a761be0b027b460c36850a9cd9df03890ce5bf833cef8c9f |
| libxml2 | 2.15.4 / he095d88_1 | 43629 | MIT | 81e8cace5c3cb62c4125882b4a6df33ab48c16349231d8ea5008bbe0ee93c10f |
| sdl | 1.2.68 / hecf2515_1 | 151496 | BSD-3-Clause | fe0780b21bd390bbd2ac167916db9db5792204cc1353ee6625bae47a12364d60 |
| numpy | 2.5.4 / py312ha3f287d_0 | 7377160 | BSD-3-Clause | 38aa0c5e5c4a7b263ea03b39f5f26fd038517571a13bcd4b9cbdef3051db5ed2 |
| cuda-libraries | 12.8.2 / h57928b3_0 | 21399 | LicenseRef-NVIDIA-End-User-License-Agreement | a3840758584fb192a62f2982400bfaf0490a988df74a67ec465dc5008f7f0962 |
| libhwloc | 2.15.0 / default_hae90fe0_1001 | 2417452 | BSD-3-Clause | 240368b73a984a1812dab5f7964ed03304950ad97466cd7ee347df9cc707629d |
| irrlicht | 1.8.5 / h20dfb44_5 | 1142127 | Zlib | aa2de7c7d1e924437438e57b5141a407bfd6a7c69ebedeb4d9f6cd07e683f724 |
| tbb | 2023.1.0 / h272cf33_2 | 157572 | Apache-2.0 | 65f5a52eb5250ca0d627e6958e703583dca008988695284fc2181b3a0a790efd |
| mkl | 2025.2.0 / hac47afa_628 | 99212321 | LicenseRef-IntelSimplifiedSoftwareOct2022 | 7b06fd311c624f607793a0f55ca2bfb24afc2bb1d9acd6d0ee4a05822db820be |
| openmpi | 4.1.3 / h8b79891_4 | 9638 | BSD-3-Clause | 7ee4f04d117673c3ebeb9dd323c360c7917401dae8554610872569cd34439bf3 |
| packaging | 26.3 / pyhc364b38_0 | 116363 | Apache-2.0 | c432626b16768b8dab228bfb706f7060c2d462a21c516d240f68f2f902b5a044 |
| setuptools | 84.2.1 / pyhe730653_0 | 567436 | MIT | 17add609d1a31c874e39a03935072be59bcafb06d42383eceabea746d12e6025 |
| cuda-runtime | 12.8.2 / h7428d3b_0 | 21291 | LicenseRef-NVIDIA-End-User-License-Agreement | df02b5ca6f9fd5e18d3c8fa56b9790a5781079d4259640d75f554407be46e76e |
| wheel | 0.48.0 / pyhd8ed1ab_0 | 34528 | MIT | ba64b29b6d418024cb565081a1799262cb2780d2534ff4c14f76aa858c4286cd |
| pip | 26.2.2 / pyh8b19718_2 | 1076882 | MIT | 27543e132e4f80285e638a08d6d90de631227186ba96901e1e069fa587d9e62f |
| pychrono | 10.0.0 / py312h418371c_0 | 527155156 | BSD 3-Clause | 8429923678c714c8b49f0a04c92990b1002457396c0765cfc250ac46fa34d92e |
