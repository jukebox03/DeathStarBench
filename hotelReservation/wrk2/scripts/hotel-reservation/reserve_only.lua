local socket = require("socket")
math.randomseed(socket.gettime() * 1000)
math.random(); math.random(); math.random()

local url = "http://localhost:5000"

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

local function make_date(day)
  if day <= 9 then
    return "2015-04-0" .. tostring(day)
  else
    return "2015-04-" .. tostring(day)
  end
end

local function reserve()
  -- 날짜: in=9~23, out=in+1~5 (최대 30일로 클램프)
  local in_day  = math.random(9, 23)
  local out_day = in_day + math.random(1, 5)
  if out_day > 30 then out_day = 30 end

  local in_date  = make_date(in_day)
  local out_date = make_date(out_day)

  local hotel_id = tostring(math.random(1, 80))
  local user_name, password = get_user()
  local customer_name = user_name

  local room_number = tostring(math.random(1, 3)) -- 1~3개 방

  local method = "POST"
  local path = url .. "/reservation"
    .. "?inDate=" .. urlencode(in_date)
    .. "&outDate=" .. urlencode(out_date)
    .. "&hotelId=" .. urlencode(hotel_id)
    .. "&customerName=" .. urlencode(customer_name)
    .. "&username=" .. urlencode(user_name)
    .. "&password=" .. urlencode(password)
    .. "&number=" .. urlencode(room_number)

  local headers = {}
  -- headers["Content-Type"] = "application/x-www-form-urlencoded"

  return wrk.format(method, path, headers, nil)
end

request = function()
  return reserve()
end
