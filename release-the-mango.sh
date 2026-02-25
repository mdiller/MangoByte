#!/bin/bash
set -e

cd /home/dillerm/.releasedmango
git pull
sudo systemctl restart mangobyte
echo "Mango released."
