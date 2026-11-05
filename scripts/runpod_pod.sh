# Source me: helpers for the RunPod SSH proxy (no scp; commands go through a PTY).
#   export POD_HOST=<pod id>-<host id>   # from `runpodctl pod get` (machine.podHostId)
#   source scripts/runpod_pod.sh; pod_put code.tgz /workspace/code.tgz; pod_run 'nvidia-smi'
: "${POD_HOST:?set POD_HOST to <pod>-<host>, e.g. abc123-64412857}"
POD_KEY=${POD_KEY:-~/.runpod/ssh/poneglyph-training-20261103}
_pod_ssh() {
  timeout "${POD_TIMEOUT:-120}" ssh -tt -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null \
    -o LogLevel=ERROR -i "$POD_KEY" "$POD_HOST@ssh.runpod.io"
}
# pod_run 'commands'  -> prints only the output between markers
pod_run() {
  { echo "stty -echo; PS1=''; PS2=''"; printf 'echo __BEGIN__; %s; echo __END__\nexit\n' "$1"; } \
    | _pod_ssh 2>&1 | tr -d '\r' | sed -n '/^__BEGIN__$/,/^__END__$/p' | sed '1d;$d'
}
# pod_put local_file remote_path
pod_put() {
  { echo "stty -echo"; echo "base64 -d > '$2' <<'B64EOF'"; base64 -w 76 "$1"; echo "B64EOF";
    echo "echo __BEGIN__; md5sum '$2'; echo __END__"; echo "exit"; } \
    | _pod_ssh 2>&1 | tr -d '\r' | sed -n '/^__BEGIN__$/,/^__END__$/p' | sed '1d;$d'
  md5sum "$1"
}
# pod_get remote_file local_file  (base64 through the terminal, checked by md5)
pod_get() {
  pod_run "base64 -w 76 '$1'" | base64 -d > "$2"
  echo "remote: $(pod_run "md5sum '$1'" | cut -d' ' -f1)  local: $(md5sum "$2" | cut -d' ' -f1)"
}
