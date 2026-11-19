#!/usr/bin/env bash
# 本机第一次登录 Betty 前装两样东西（要 sudo，只跑一次）：
#   1. Kerberos 工具 krb5-user（kinit），默认 realm 设成 UPENN.EDU（Penn 的 KDC 由 DNS 自动找到）；
#   2. GlobalProtect VPN 客户端。Penn 的入口 vpn.upenn.edu 用浏览器单点登录（PennKey + Duo），
#      普通 openconnect 不支持，这里装开源的 globalprotect-openconnect（yuezk 的 PPA，有 Ubuntu 24.04 版）。
#      不想用第三方客户端的话，可以到 Penn ISC 网站登录后下载官方 Linux 版 GlobalProtect，跳过第 2 步。
set -euo pipefail
echo ">> 1/2 Kerberos"
echo "krb5-config krb5-config/default_realm string UPENN.EDU" | sudo debconf-set-selections
sudo apt-get update -q
sudo DEBIAN_FRONTEND=noninteractive apt-get install -y -q krb5-user
echo ">> 2/2 GlobalProtect VPN 客户端"
sudo add-apt-repository -y ppa:yuezk/globalprotect-openconnect
sudo apt-get update -q
sudo apt-get install -y -q globalprotect-openconnect
echo ">> 装好了：$(command -v kinit) $(command -v gpclient || command -v gpgui || echo '（VPN 客户端在应用菜单里叫 GlobalProtect）')"
