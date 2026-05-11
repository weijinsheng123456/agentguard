#!/bin/bash
# install.sh — 质量门禁 v5 一键安装（Python版）

set -e

QG_HOME="$(cd "$(dirname "$0")" && pwd)"
HERMES_HOME="${HERMES_HOME:-$HOME/.hermes}"
GATE_PY="$QG_HOME/gate.py"

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; CYAN='\033[0;36m'; NC='\033[0m'
log() { echo -e "${CYAN}[$(date '+%H:%M:%S')]${NC} $1"; }

echo ""
echo -e "${CYAN}════════════════════════════════════════${NC}"
echo -e "${CYAN}  Hermes 质量门禁 v5 — 一键安装${NC}"
echo -e "${CYAN}════════════════════════════════════════${NC}"
echo ""

# Step 1: 目录
log "📁 创建目录结构..."
mkdir -p "$QG_HOME"/{qg/rules,hooks,backups,scripts}
log "${GREEN}  ✅ 目录已就绪${NC}"

# Step 2: 权限
log "🔐 设置执行权限..."
chmod +x "$GATE_PY" 2>/dev/null || true
chmod +x "$QG_HOME/scripts/gate" 2>/dev/null || true
chmod +x "$QG_HOME/hooks/pre-commit" 2>/dev/null || true
log "${GREEN}  ✅ 权限已设置${NC}"

# Step 3: 链接到 PATH
log "🔗 链接到 PATH..."
for link_target in "$HOME/.local/bin/gate" "$HERMES_HOME/bin/gate"; do
    mkdir -p "$(dirname "$link_target")"
    ln -sf "$GATE_PY" "$link_target"
done
log "${GREEN}  ✅ gate -> $GATE_PY${NC}"

# Step 4: 安装 pre-commit 钩子
log "🔧 安装 pre-commit 钩子..."
HOOK_SRC="$QG_HOME/hooks/pre-commit"
for scan_dir in $(python3 -c "import yaml; import os; c=yaml.safe_load(open(os.path.expanduser('$QG_HOME/config.yaml'))); print(' '.join(c.get('scan_dirs',[])))" 2>/dev/null); do
    expanded="${scan_dir/#\~/$HOME}"
    expanded="${expanded/#\$HOME/$HOME}"
    # 向上查找 .git
    dir="$expanded"
    while [ "$dir" != "/" ]; do
        if [ -d "$dir/.git" ]; then
            cp "$HOOK_SRC" "$dir/.git/hooks/pre-commit" 2>/dev/null && \
                chmod +x "$dir/.git/hooks/pre-commit" 2>/dev/null && \
                log "  ✅ 钩子已安装: $(basename "$dir")"
            break
        fi
        dir="$(dirname "$dir")"
    done
done

# Step 5: 更新/创建 Cron（改用 Python 版）
log "⏰ 配置 Cron 任务..."
CRON_JOB="0 7 * * * cd $HOME && python3 $GATE_PY run 2>&1 >> $HERMES_HOME/logs/quality-gate-cron.log"
if crontab -l 2>/dev/null | grep -q "quality-gate"; then
    (crontab -l 2>/dev/null | grep -v "quality-gate"; echo "$CRON_JOB") | crontab -
    log "${GREEN}  ✅ Cron 已更新${NC}"
else
    (crontab -l 2>/dev/null || true; echo "$CRON_JOB") | crontab -
    log "${GREEN}  ✅ Cron 已添加: 每天 07:00${NC}"
fi

# Step 6: 初始化 manifest
log "🗂️  初始化文件清单..."
python3 "$GATE_PY" run 2>&1 | tail -5 || true
log "${GREEN}  ✅ 首次扫描完成${NC}"

echo ""
echo -e "${GREEN}════════════════════════════════════════${NC}"
echo -e "${GREEN}  质量门禁 v5 安装完成！${NC}"
echo -e "${GREEN}════════════════════════════════════════${NC}"
echo ""
echo -e "  ${CYAN}使用方式:${NC}"
echo -e "    gate run            完整扫描+修复+提交"
echo -e "    gate run --quick    快速检查(staged文件)"
echo -e "    gate run --fixme    修复当前变更"
echo -e "    gate install        重新安装"
echo ""
echo -e "  ${CYAN}每日 Cron:${NC} 07:00 自动运行"
echo -e "  ${CYAN}Pre-commit:${NC} 提交时自动检查"
echo ""
