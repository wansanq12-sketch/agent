"""Local, persistent water/movement reminder clocks; no model calls or system notifications."""
import json
import secrets
from database import connection
import threading
import time

KINDS={'water':('water_reminder_enabled','water_reminder_interval'),'move':('move_reminder_enabled','move_reminder_interval')}
GAP_MS=5*60000
DISPLAY_MS=30000

class ReminderService:
    def __init__(self,database,config,clock=None):
        self.database=database;self.config=config;self.clock=clock or (lambda:int(time.time()*1000));self.lock=threading.RLock()
        with connection(database) as db:db.execute('CREATE TABLE IF NOT EXISTS reminder_schedule(id INTEGER PRIMARY KEY CHECK(id=1),value TEXT NOT NULL)')

    def _save(self,state):
        with connection(self.database) as db:db.execute('INSERT OR REPLACE INTO reminder_schedule VALUES (1,?)',(json.dumps(state),))

    def _load(self,now):
        with connection(self.database) as db:row=db.execute('SELECT value FROM reminder_schedule WHERE id=1').fetchone()
        state=json.loads(row[0]) if row else {'last_shown':0,'active':None}
        config=self.config.snapshot();changed=not bool(row)
        for kind,(enable,interval) in KINDS.items():
            current=state.get(kind)
            if current is None or current.get('enabled')!=config[enable] or current.get('interval')!=config[interval]:
                state[kind]={'enabled':config[enable],'interval':config[interval],'next_due':now+config[interval]*60000};changed=True
        active=state.get('active')
        if active and (active['expires_at']<=now or not state[active['kind']]['enabled']):state['active']=None;changed=True
        if changed:self._save(state)
        return state

    def status(self):
        with self.lock:
            state=self._load(self.clock())
            return {key:state[key] for key in ('water','move','active','last_shown')}

    def poll(self,hour,blocked=False):
        if type(hour) is not int or not 0<=hour<=23:raise ValueError('提醒时段参数无效')
        with self.lock:
            now=self.clock();state=self._load(now);config=self.config.snapshot()
            a,b=config['quiet_start'],config['quiet_end'];quiet=False if a==b else (a<=hour<b if a<b else hour>=a or hour<b)
            if blocked or quiet:return None
            if state['active']:return dict(state['active'])
            if state['last_shown'] and now-state['last_shown']<GAP_MS:return None
            due=[kind for kind in KINDS if state[kind]['enabled'] and state[kind]['next_due']<=now]
            if not due:return None
            kind=min(due,key=lambda key:state[key]['next_due'])
            reminder={'id':secrets.token_urlsafe(16),'kind':kind,'expires_at':now+DISPLAY_MS,'previous_last_shown':state['last_shown']}
            state['active']=reminder;state['last_shown']=now
            # A long pause produces one reminder, never a backlog of overdue messages.
            state[kind]['next_due']=now+state[kind]['interval']*60000
            self._save(state);return dict(reminder)

    def respond(self,request_id,action):
        if action not in ('done','skip','snooze','defer'):raise ValueError('未知提醒操作')
        with self.lock:
            now=self.clock();state=self._load(now);active=state['active']
            if not active or active['id']!=request_id:raise ValueError('这条提醒已结束')
            kind=active['kind'];minutes=1 if action=='defer' else 10 if action=='snooze' else state[kind]['interval']
            state[kind]['next_due']=now+minutes*60000
            if action=='defer':state['last_shown']=active.get('previous_last_shown',0)
            state['active']=None;self._save(state);return {'ok':True}
