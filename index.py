import os
import logging
import wsgiref.handlers
from google.appengine.ext import webapp
from google.appengine.ext.webapp import template
from util.sessions import Session
from google.appengine.ext import db

# A Model for a User
# 유저 정보 처리하기위한 클래스
# 데이터베이스를 사용하여 처리함
class User(db.Model):
  account = db.StringProperty()
  password = db.StringProperty()
  name = db.StringProperty()

# A Model for a ChatMessage
# DB에서 유저 이름과 메세지 내용을 가져옴
class ChatMessage(db.Model):
  user = db.ReferenceProperty()
  text = db.StringProperty()
  created = db.DateTimeProperty(auto_now=True)

# A helper to do the rendering and to add the necessary
# variables for the _base.htm template
#
def doRender(handler, tname = 'index.htm', values = { }):
    # templates/index.htm 파일 있는지 확인
  temp = os.path.join(
      os.path.dirname(__file__),
      'templates/' + tname)
  if not os.path.isfile(temp):
      # 파일이 없으면 return False
    return False

  # Make a copy of the dictionary and add the path and session
  newval = dict(values)
  newval['path'] = handler.request.path
  handler.session = Session()
  if 'username' in handler.session:
     newval['username'] = handler.session['username']
  #template 렌더 후 함수 종료
  outstr = template.render(temp, newval)
  handler.response.out.write(unicode(outstr))
  return True

# 로그인을 다루는 클래스
class LoginHandler(webapp.RequestHandler):
  #get 형식의 요청에 loginscreen.htm을 렌더하여 대응
  def get(self):
    doRender(self, 'loginscreen.htm')
  #post 형식의 요청에 대응하여 세션을 생성
  def post(self):
    self.session = Session()
    acct = self.request.get('account')
    pw = self.request.get('password')
    logging.info('Checking account='+acct+' pw='+pw)

    self.session.delete_item('username')
    self.session.delete_item('userkey')
    # 빈칸이면 error메세지
    if pw == '' or acct == '':
      doRender(
          self,
          'loginscreen.htm',
          {'error' : 'Please specify Account and Password'} )
      return
    #DB에서 account와 password 가져오는 과정
    que = db.Query(User)
    que = que.filter('account =',acct)
    que = que.filter('password = ',pw)

    results = que.fetch(limit=1)
    # 정상적으로 입력되었을 때 user.key()와 acct값을 세션에 삽입
    if len(results) > 0 :
      user = results[0]
      self.session['userkey'] = user.key()
      self.session['username'] = acct
      doRender(self,'index.htm',{ } )
    #정보 오류시 오류메세지 출력
    else:
      doRender(
          self,
          'loginscreen.htm',
          {'error' : 'Incorrect password'} )

# 새로운 계정 생성을 다루는 클래스
class ApplyHandler(webapp.RequestHandler):
  #get 형식의 요청에 applyscreen.htm을 렌더하여 대응한다
  def get(self):
    doRender(self, 'applyscreen.htm')
  #post 형식의 요청에 대응하여 세션 생성, 입력받은 정보를 저장한다
  def post(self):
    self.session = Session()
    name = self.request.get('name')
    acct = self.request.get('account')
    pw = self.request.get('password')
    logging.info('Adding account='+acct)
    # 내용이 비어있으면 error
    if pw == '' or acct == '' or name == '':
      doRender(
          self,
          'applyscreen.htm',
          {'error' : 'Please fill in all fields'} )
      return

    # Check if the user already exists
    # 이름으로 확인
    que = db.Query(User).filter('account =',acct)
    results = que.fetch(limit=1)

    if len(results) > 0 :
      doRender(
          self,
          'applyscreen.htm',
          {'error' : 'Account Already Exists'} )
      return

    # Create the User object and log the user in
    # 입력받은 정보로 새 객체 생성하여 정보와 기본키 값을 만들어서 삽입
    newuser = User(name=name, account=acct, password=pw);
    pkey = newuser.put();
    self.session['username'] = acct
    self.session['userkey'] = pkey
    doRender(self,'index.htm',{ })

#
class MembersHandler(webapp.RequestHandler):
 #get 형식의 요청에 대응하여 DB에서 멤버 리스트를 최대 100개까지 불러온 후 memberscreen.htm을 렌더함
  def get(self):
    que = db.Query(User)
    user_list = que.fetch(limit=100)
    doRender(
        self, 
        'memberscreen.htm', 
        {'user_list': user_list})

class ChatHandler(webapp.RequestHandler):
#get 형식의 요청에 chatscreen.htm을 렌더하여 대응
  def get(self):
    doRender(self,'chatscreen.htm')
#post 형식의 요청이 왔을 때 세션에 userkey가 없으면 error
#userkey가 있을 때는 메세지를 가져와서 비어 있으면 error,
#내용이 있으면 ChatMessage 객체 생성하여 저장
  def post(self):
    self.session = Session()
    if not 'userkey' in self.session:
      doRender(
          self,
          'chatscreen.htm',
          {'error' : 'Must be logged in'} )
      return

    msg = self.request.get('message')
    if msg == '':
      doRender(
          self,
          'chatscreen.htm',
          {'error' : 'Blank message ignored'} )
      return

    newchat = ChatMessage(user = self.session['userkey'], text=msg)
    newchat.put();
    doRender(self,'chatscreen.htm')

class MessagesHandler(webapp.RequestHandler):
# get 형식의 요청에 대응하여 ChatMeassage를 DB에서 가져와
# 생성된지 가장 오래된것부터 큐에 저장 (최대 10개까지)
# messagelist.htm 렌더한다
  def get(self):
    que = db.Query(ChatMessage).order('-created');
    chat_list = que.fetch(limit=10)
    doRender(self, 'messagelist.htm', {'chat_list': chat_list})

class LogoutHandler(webapp.RequestHandler):
# get 형식의 요청에 대응하여 세션 정보를 제거하는 기능
  def get(self):
    self.session = Session()
    self.session.delete_item('username')
    self.session.delete_item('userkey')
    doRender(self, 'index.htm')

class MainHandler(webapp.RequestHandler):
#get 형식의 요청에 대응하여 getReder()의 반환값이 True
#이면 정상적으로 종료, 아니면 다시 렌더
  def get(self):
    if doRender(self,self.request.path) :
      return
    doRender(self,'index.htm')
# 경로 설정
def main():
  application = webapp.WSGIApplication([
     ('/login', LoginHandler),
     ('/apply', ApplyHandler),
     ('/members', MembersHandler),
     ('/chat', ChatHandler),
     ('/messages', MessagesHandler),
     ('/logout', LogoutHandler),
     ('/.*', MainHandler)],
     debug=True)
  wsgiref.handlers.CGIHandler().run(application)

if __name__ == '__main__':
  main()
