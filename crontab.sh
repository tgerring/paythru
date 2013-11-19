#!/bin/bash
JSONPRICES=$(curl http://api.bitcoincharts.com/v1/weighted_prices.json)
curl -X POST -d "$JSONPRICES" http://localhost:8080/blocklatest