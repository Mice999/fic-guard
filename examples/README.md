# examples

`sample.txt` 是一段虚构的、用于演示工具流程的中文文本。可以用它端到端跑一遍：

```bash
fic-guard fingerprint make examples/sample.txt --work-id demo --count 3 --seed 1
fic-guard fingerprint show .fic-guard/demo.fingerprint.json
fic-guard timestamp make examples/sample.txt --work-id demo
fic-guard fingerprint watermark examples/sample.txt --payload site-A --output /tmp/sample.site-A.txt
fic-guard fingerprint extract /tmp/sample.site-A.txt
fic-guard monitor .fic-guard/demo.fingerprint.json
```
