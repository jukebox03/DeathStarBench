local socket = require("socket")
math.randomseed(socket.gettime() * 1000)
math.random(); math.random(); math.random()

local url = "http://localhost:5000"

-- 최소 URL 인코딩 (이 스크립트의 username/password는 특수문자 없지만 안전하게 넣어둠)
local function urlencode(str)
  return (tostring(str):gsub("([^%w%-_%.~])", function(c)
    return string.format("%%%02X", string.byte(c))
  end))
end

local function get_user()
  local id = math.random(0, 500)
  local user_name = "Cornell_" .. tostring(id)

  local pass_word = ""
  for i = 1, 10 do
    pass_word = pass_word .. tostring(id)
  end

  return user_name, pass_word
end

request = function()
  local user_name, password = get_user()

  local method = "POST"
  local path = url .. "/user?username=" .. urlencode(user_name) .. "&password=" .. urlencode(password)

  local headers = {}
  -- headers["Content-Type"] = "application/x-www-form-urlencoded"

  return wrk.format(method, path, headers, nil)
end
