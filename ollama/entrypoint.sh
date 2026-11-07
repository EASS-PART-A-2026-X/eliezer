#!/bin/sh
# Start the Ollama server. Then, in the background, download the model named in
# AI_MODEL ("ollama:<model>") if the /models volume does not have it yet, and set
# its CPU thread count. The server answers (and the healthcheck passes) meanwhile.
set -u

ollama serve &
server=$!
trap 'kill -TERM "$server" 2> /dev/null' TERM INT # let "docker stop" stop it cleanly

download() {
  for attempt in 1 2 3; do
    echo "Downloading $1 (only the first time), attempt $attempt of 3..."
    ollama pull "$1" && return 0
    sleep 30
  done
  echo "Could not download $1. Check the network and free disk space, then run:" \
    "docker compose restart ollama" >&2
  return 1
}

# Ollama starts one thread per CPU. Inside Docker Desktop's VM, on a laptop that
# is busy with other apps, those threads keep waiting for each other: measured on
# a 12-thread laptop, 12 threads wrote 0.3-0.7 tokens/s and 4 threads 7.6. The
# AI service talks the OpenAI API, which cannot pass Ollama options, so the count
# is stored as a default in the model itself (only a small settings file changes).
set_threads() {
  modelfile="$(mktemp)"
  printf 'FROM %s\nPARAMETER num_thread %s\n' "$1" "$2" > "$modelfile"
  if ollama create "$1" -f "$modelfile" > /dev/null; then
    echo "$1 is ready ($2 CPU threads)"
  fi
  rm -f "$modelfile"
}

prepare() {
  until ollama list > /dev/null 2>&1; do sleep 1; done # wait for the server
  case "${AI_MODEL:-}" in
    ollama:*) model="${AI_MODEL#ollama:}" ;;
    *)
      echo "AI_MODEL=${AI_MODEL:-} is not an Ollama model: nothing to download"
      return
      ;;
  esac
  if ! ollama show "$model" > /dev/null 2>&1; then
    download "$model" || return
  fi
  set_threads "$model" "${OLLAMA_NUM_THREAD:-4}"
}
prepare &

# "wait" returns early when a signal arrives, so wait until the server is gone.
status=0
while kill -0 "$server" 2> /dev/null; do
  wait "$server"
  status=$?
done
exit "$status"
