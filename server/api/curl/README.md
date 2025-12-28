用来测试API接口的：

fetch("http://localhost:5001/api/user/me", {
  "headers": {
    "accept": "*/*",
    "accept-language": "zh,zh-CN;q=0.9,en-US;q=0.8,en;q=0.7",  
    "content-type": "application/json",   
    "sec-ch-ua": "\"Google Chrome\";v=\"135\", \"Not-A.Brand\";v=\"8\", \"Chromium\";v=\"135\"",
    "sec-ch-ua-mobile": "?0",
    "sec-ch-ua-platform": "\"macOS\"",
    "sec-fetch-dest": "empty",
    "sec-fetch-mode": "cors",
    "sec-fetch-site": "same-site",
    "userid": "LtXQ0x62DpOB88r1x3TL329FbHk1"
  },
  "referrer": "http://localhost:3000/",
  "referrerPolicy": "strict-origin-when-cross-origin",  
  "method": "PUT",
  "mode": "cors",
  "credentials": "omit",
  "body": JSON.stringify({
    "display_name": "New Display Name",
    "email": "new.email@example.com",
    "profile_picture": "https://example.com/new-profile-picture.jpg",
    "preferences": {
      "theme": "dark",
      "notifications": true
    }
  })
});



fetch("http://localhost:5001/api/user/me", {
  "headers": {
    "accept": "*/*",
    "accept-language": "zh,zh-CN;q=0.9,en-US;q=0.8,en;q=0.7",  
    "content-type": "application/json",   
    "sec-ch-ua": "\"Google Chrome\";v=\"135\", \"Not-A.Brand\";v=\"8\", \"Chromium\";v=\"135\"",
    "sec-ch-ua-mobile": "?0",
    "sec-ch-ua-platform": "\"macOS\"",
    "sec-fetch-dest": "empty",
    "sec-fetch-mode": "cors",
    "sec-fetch-site": "same-site",
    "userid": "LtXQ0x62DpOB88r1x3TL329FbHk1"
  },
  "referrer": "http://localhost:3000/",
  "referrerPolicy": "strict-origin-when-cross-origin",  
  "method": "GET",
  "mode": "cors",
  "credentials": "omit"
});