# SL-013 atomic extract / CLI error 実装計画

## 目的

extract成果物をsibling stagingで完成・検証してからproject単位でswapし、process内の途中失敗で
旧projectとannotationsを失わない。CLIの利用者修復可能なdata/I/O errorを統一表示する。

## 設計

- project親に固定suffixのstage、backup、exclusive lockを置き、残存時は自動削除せず停止する。
- projectと管理pathのsymlinkを拒否し、未知symlinkは`copytree(symlinks=True)`で展開しない。
- 既存project全体をstageへ複製し、stage内のstructureだけを削除・再生成する。
- raw、manifest、catalog、README、questions、sheet Markdown、必要なVBAをstageで再読込検証する。
- 新規projectはstageをrenameする。既存projectはproject→backup、stage→projectとrenameし、
  2回目失敗時はbackup→projectでrollbackする。
- rollback失敗時はstage/backup/lockを保持して手動復旧pathを例外へ含める。
- swap後のbackup削除失敗は生成済みprojectを失敗扱いせず、後処理警告として報告する。
- この契約はprocess内失敗のrollbackであり、2 rename間の電源断まで完全atomicとはしない。
- CLIはdomain exceptionを先に処理し、その後JSON/Pydantic/Unicode/OSErrorをpathと復旧方法付き
  exit 1へ変換する。post-commit cleanup warningは別扱いにする。

## 実装手順

1. stage生成失敗、validation失敗、rename/rollback、cleanup、stale/symlinkのfailure injectionを追加する。
2. atomic staging・validation・swap helperをpipelineへ実装する。
3. compile/checkの壊れたrawとI/O errorをCLI error contractでテスト・実装する。
4. 関連テスト、全テスト、lint、project-state、advisor reviewを完了する。
