local socket = require("socket")
math.randomseed(socket.gettime() * 1000)
math.random(); math.random(); math.random()

local url = "http://localhost:5000"

-- 고정된 파라미터로 cache hit ratio = 1
local in_date_str = "2015-04-10"
local out_date_str = "2015-04-11"
local lat = 38.0235
local lon = -122.095

request = function()
  local method = "GET"
  local path = url .. "/hotels?inDate=" .. in_date_str ..
    "&outDate=" .. out_date_str .. "&lat=" .. tostring(lat) .. "&lon=" .. tostring(lon)

  local headers = {}
  return wrk.format(method, path, headers, nil)
end