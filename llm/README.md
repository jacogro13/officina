# Local model server (llama.cpp)

The systemd units that serve every model used by officina and Brio, as they run on my
server: a GMKtec NucBox EVO-X1 (AMD Ryzen AI 9 HX 370, Radeon 890M iGPU, 32 GB
LPDDR5-7500). The BIOS reserves 4 GiB as VRAM; the iGPU can borrow up to 24 GiB more of
the ~27 GiB system RAM (GTT), so models of 13–15 GB run fully on the GPU (`-ngl 99`)
while CPU and GPU share that memory. Each unit is one `llama-server` instance (llama.cpp
build 9780, Vulkan backend) with an OpenAI-compatible API, running on the host rather
than in Docker.
The user and paths in the units (`llama`, `/opt/...`) are examples; everything else is
what runs.

| Unit | Port | Model | Context | Used for | At boot |
|---|---|---|---|---|---|
| `llama.service` | 8080 | Gemma 4 26B-A4B `UD-Q4_K_XL`, text only | 32k | chat in the apps (Brio) | yes |
| `llama-qwen.service` | 8080 | Qwen3.6-35B-A3B `UD-IQ3_XXS` (13.2 GB) | 16k | officina's local worker | no |
| `llama-vision.service` | 8081 | Gemma 4 E4B `Q4_K_M` (with vision projector) | 8k | image import | yes |
| `llama-embed.service` | 8082 | Qwen3-Embedding-0.6B `Q8_0` | 4k | embeddings for RAG | yes |
| `llama-ocr.service` | 8083 | GLM-OCR 0.9B `Q8_0` | 16k, 2 slots | text and code from book pages | yes |

## Why five instances

- **One role per server.** A `llama-server` instance either generates or serves
  embeddings, and the big text model runs without its vision projector (see below), so
  vision, embeddings and OCR each get their own small instance.
- **Two big models, one at a time.** Gemma (~15 GiB) and Qwen (~13 GB plus KV cache)
  don't fit together. `llama-qwen.service` has `Conflicts=llama.service`, so starting
  one stops the other, and it has no `[Install]` section: after a reboot it's always
  Gemma. While Qwen is loaded, the apps get Qwen's answers on port 8080.
- **A stable model id.** `--alias qwen-code` gives the worker a name it checks before it
  takes a task (`/v1/models`).

## Lessons from running it

- **Prompt cache vs. memory:** `--cache-ram` defaults to 8 GiB. On a shared-memory APU
  it stacks on top of the weights and the 32k KV cache and can get the server killed
  for lack of memory during a long batch job. With a different prompt per request the
  cache buys almost nothing there, so it's off (`--cache-ram 0`).
- **GPU hang in the Vulkan backend** (llama.cpp #24861): with a vision projector, large
  graphs wedge the 890M's compute ring and `llama-server` segfaults. Workarounds: the big
  model runs `--no-mmproj`, the vision model uses a small context, and the OCR model
  keeps its projector on the CPU (`--no-mmproj-offload`). The full error trace is in
  `llama-ocr.service`.
- **`--parallel` splits the context:** `-c` is the total KV cache, so two slots with
  `-c 16384` give 8k tokens per request.
- **Headroom for the coding model:** a quantised KV cache (`-ctk q8_0 -ctv q8_0`, needs
  `-fa on`), and `OOMScoreAdjust=1000` so that under memory pressure the kernel kills
  this process first, never the database. `Restart=no`: if it dies, it stays down.

## Network

The units bind `--host 0.0.0.0`. App containers reach them through their Docker
network's gateway (`10.100.0.1`, a pinned subnet); the factory worker on my laptop
reaches Qwen over the LAN. The servers have **no authentication**, so this relies on
the LAN not being reachable from outside. To keep a model off the LAN, bind it to the
gateway address instead.

## Install

```bash
# llama.cpp with the Vulkan backend
git clone https://github.com/ggml-org/llama.cpp /opt/llama.cpp && cd /opt/llama.cpp
cmake -B build -DGGML_VULKAN=ON && cmake --build build --config Release -j

# a unit (adjust User= and paths first)
sudo cp llama.service /etc/systemd/system/
sudo systemctl daemon-reload && sudo systemctl enable --now llama.service
curl -s http://localhost:8080/v1/models
```

The `-hf` units download their model on first start. `llama-qwen.service` expects
`Qwen3.6-35B-A3B-UD-IQ3_XXS.gguf` (from `unsloth/Qwen3.6-35B-A3B-GGUF` on Hugging Face)
in `/opt/models/`. Swapping models:

```bash
sudo systemctl start llama-qwen.service   # → Qwen (stops Gemma)
sudo systemctl start llama.service        # → back to Gemma (stops Qwen)
```
