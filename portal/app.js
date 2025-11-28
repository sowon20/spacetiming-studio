document.getElementById('send').onclick = () => {
  const msg = document.getElementById('msg').value;
  if (!msg.trim()) return;
  const log = document.getElementById('chat-log');
  const div = document.createElement('div');
  div.textContent = "You: " + msg;
  log.appendChild(div);
  document.getElementById('msg').value = "";
  log.scrollTop = log.scrollHeight;
};
