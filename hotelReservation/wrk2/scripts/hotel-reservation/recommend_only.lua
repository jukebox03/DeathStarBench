local socket = require("socket")
math.randomseed(socket.gettime() * 1000)
math.random(); math.random(); math.random()

local url = "http://localhost:5000"

-- 고정된 recommendation 요청 (cache hit ratio = 1)
local function recommend()
  -- 항상 동일한 require / lat / lon
  local req_param = "dis"
  local lat = 38.0235
  local lon = -122.095

  local method = "GET"
  local path = url .. "/recommendations?require=" .. req_param ..
               "&lat=" .. tostring(lat) ..
               "&lon=" .. tostring(lon)

  local headers = {}
  -- headers["Content-Type"] = "application/x-www-form-urlencoded"

  return wrk.format(method, path, headers, nil)
end

request = function()
  return recommend()
end
