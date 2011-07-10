#!/usr/bin/env python
# -*- coding: utf-8 -*-

from flask import Flask, Blueprint, redirect, render_template, url_for, \
     _request_ctx_stack
from flaskext.script import Command, Manager, Option
from flaskext.sqlalchemy import SQLAlchemy
from flaskext.xmlrpc import XMLRPCHandler
import inspect, os, re, sys

_re_acronyms_syntax = re.compile(r'^(?P<acronym>[^\$ \t]+) *\t*(?P<translation>.+)$')


### Models ###

db = SQLAlchemy()

class WTF(db.Model):
    '''Basic model for WTF acronyms.'''
    
    __tablename__ = 'wtf'
    
    id = db.Column(db.Integer, primary_key=True)
    acronym = db.Column(db.String(15), unique=False)
    translation = db.Column(db.String(300))
    
    def __init__(self, acronym, translation):
        self.acronym = acronym.upper()
        self.translation = translation
    
    def __repr__(self):
        return '<WTF is %s? "%s">' % (self.acronym, self.translation)


### Script commands ###

class PopulateDB(Command):
    '''Populate the database using data from a wtf acronym file.'''

    option_list = (
        Option('--file', '-f', dest='acronyms_file', required=True, metavar='FILE'),
    )
    
    def run(self, acronyms_file):        
        if not os.path.exists(acronyms_file) and not os.path.isfile(acronyms_file):
            sys.exit('Invalid acronym file: %r' % acronyms_file)
        db.create_all()
        with open(acronyms_file, 'r') as fp:
            try:
                for line in fp:
                    rv = _re_acronyms_syntax.match(line)
                    if rv is not None:
                        rv = rv.groupdict()
                        results = WTF.query.filter_by(acronym=rv['acronym']).all()
                        exists = False
                        for result in results:
                            if result.translation == rv['translation']:
                                exists = True
                        if not exists:
                            db.session.add(WTF(**rv))
            except:
                db.session.rollback()
                sys.exit('Failed to populate the database.')
            else:
                db.session.commit()
    

### API functions ###

api = XMLRPCHandler('api')

@api.register('wtf_is')
def translate(acronym):
    '''Returns a list of translations available for `acronym`.'''
    try:
        results = WTF.query.filter_by(acronym=acronym.upper()).all()
    except:
        results = []
    return [i.translation for i in results]

@api.register('list')
def list_all():
    '''Returns a list of acronyms available on the server.'''
    try:
        results = WTF.query.group_by(WTF.acronym).order_by(WTF.acronym).all()
    except:
        results = []
    return [i.acronym for i in results]


### Views ###

views = Blueprint('views', __name__)

@views.route('/')
def home():
    return render_template('main.html')

@views.route('/acronyms')
def acronyms():
    results = WTF.query.order_by(WTF.acronym).all()
    return render_template('list.html', acronyms=results)

@views.route('/api')
def api_doc():
    funcs = []
    for func in api.funcs:
        if not func.startswith('system.'):
            funcs.append((
                func,
                # TODO: improve introspection
                inspect.getargspec(api.funcs[func]),
                inspect.getdoc(api.funcs[func])
            ))
    return render_template('api.html', funcs=funcs)

@views.route('/RPC2')
def rpc2():
    return redirect(url_for('views.api_doc'))


### Factories ###

def create_app(database=None):
    
    if database is None:
        database = '/tmp/wtf-server.db'
    
    app = Flask(__name__)
    
    # I hate everything but SQLite3 :P
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///%s' % database
    
    api.connect(app, '/RPC2')
    db.init_app(app)
    app.register_blueprint(views)
    
    return app

def create_script():
    
    manager = Manager(create_app, with_default_commands=True)
    manager.add_option('-d', '--database', dest='database', required=False)
    manager.add_command('populate', PopulateDB())
    
    @manager.shell
    def _make_context():
        return dict(app=_request_ctx_stack.top.app, db=db, WTF=WTF)
    
    return manager


if __name__ == '__main__':
    script = create_script()
    script.run()
