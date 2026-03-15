FROM lscr.io/linuxserver/openssh-server:latest
RUN apk add --no-cache iptables ip6tables
# The container's init overwrites sudoers, so we use a custom init script
# that runs after the default init to set NOPASSWD
COPY init-nopasswd-sudo.sh /custom-cont-init.d/init-nopasswd-sudo.sh
RUN chmod +x /custom-cont-init.d/init-nopasswd-sudo.sh
