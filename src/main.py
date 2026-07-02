# -*- coding: utf-8 -*-

import hmac
import os
import uuid
import csv
import io

from flask import Flask, request, jsonify, Response, render_template_string
from loguru import logger

from markupsafe import escape

from utils import config as cfg_utils
from utils import emails
from db import utils as db_utils
from utils.emailer import EmailClient
from services.matching import MatchingService
from services.responses import ResponseService
from models.user import User
from constants.common import ACTIVITY_LABELS
from db.exceptions import UserNotFoundError

CONFIG_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "../resources/config.yml"))
config = cfg_utils.load(CONFIG_PATH)
user_repo, meet_repo, metadata_repo, match_response_repo = db_utils.get_repos(config)

email_client = EmailClient(config, dry_run=config["notifications"].get("dryRun", True))
matching_service = MatchingService(config, user_repo, meet_repo, metadata_repo, email_client)
response_service = ResponseService(config, meet_repo, match_response_repo, user_repo, email_client)

app = Flask(__name__, static_folder=os.path.join(os.path.dirname(__file__), 'static'))
app.config["ADMIN_TOKEN"] = config["app"].get("adminToken")

LIFE_CONTEXT_OPTIONS = ["New here", "Works from home", "Has kids", "Pet owner"]

HOME_TEMPLATE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Community Coffee — {{ community_name }}</title>
<style>
*,*::before,*::after{box-sizing:border-box;margin:0;padding:0}
:root{
  --bg:#f4efe7;--text:#151711;--muted:#34382f;--subtle:#5e6459;
  --primary:#143c32;--primary-dk:#0f2f28;--green-light:#edf5f0;
  --border:rgba(21,23,17,0.1);--white-glass:rgba(255,255,255,0.45);
}
html{scroll-behavior:smooth}
body{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;background:var(--bg);color:var(--text);min-height:100vh;overflow-x:hidden}
a{color:inherit;text-decoration:none}
button,input,textarea,select{font:inherit}

/* MODAL */
.modal{position:fixed;inset:0;z-index:50;overflow-y:auto;background:rgba(244,239,231,0.92);backdrop-filter:blur(24px);-webkit-backdrop-filter:blur(24px);padding:2rem 1.25rem;display:none}
.modal.open{display:block}
.modal-inner{max-width:72rem;margin:0 auto}
.modal-bar{display:flex;align-items:center;justify-content:space-between;margin-bottom:1.5rem}
.btn-back{border:1px solid var(--border);background:rgba(255,255,255,0.55);border-radius:100px;padding:.5rem 1rem;font-size:.875rem;font-weight:600;cursor:pointer;backdrop-filter:blur(24px);box-shadow:inset 0 1px 0 rgba(255,255,255,.85)}
.modal-brand{display:flex;align-items:center;gap:.5rem;border:1px solid var(--border);background:rgba(255,255,255,0.45);border-radius:100px;padding:.5rem 1rem;font-size:.875rem;font-weight:600;backdrop-filter:blur(24px)}
.modal-card{position:relative;overflow:hidden;border-radius:3rem;border:1px solid rgba(255,255,255,0.75);background:rgba(255,255,255,0.34);padding:2rem;box-shadow:inset 0 1px 0 #fff,0 34px 95px rgba(17,24,39,0.16);backdrop-filter:blur(36px)}
.modal-card::before{content:'';position:absolute;inset:0;background:radial-gradient(circle at 88% 18%,rgba(216,238,229,0.9),transparent 32%),radial-gradient(circle at 12% 82%,rgba(234,214,189,0.9),transparent 38%),linear-gradient(135deg,#f8f2e9 0%,#ecdfcf 44%,#d8e6dd 100%);pointer-events:none}
.modal-grid{position:relative;display:grid;gap:2rem}
@media(min-width:1024px){.modal-grid{grid-template-columns:.9fr 1.1fr;align-items:start}}
.modal-left{padding-top:.5rem}
.modal-tag{font-size:.75rem;font-weight:700;letter-spacing:.24em;text-transform:uppercase;color:var(--primary);margin-bottom:1rem}
.modal-h1{font-size:2.5rem;font-weight:600;line-height:.98;letter-spacing:-.055em;margin-bottom:1.25rem}
@media(min-width:768px){.modal-h1{font-size:3rem}}
.modal-sub{font-size:1rem;line-height:2;color:var(--muted);margin-bottom:2rem;max-width:32rem}
.check-list{display:grid;gap:.75rem;margin-bottom:2rem}
.check-item{display:flex;align-items:center;gap:.75rem;border:1px solid var(--border);background:rgba(255,255,255,0.45);border-radius:1rem;padding:.75rem 1rem;font-size:.875rem;font-weight:600;color:var(--muted);box-shadow:inset 0 1px 0 rgba(255,255,255,.9);backdrop-filter:blur(24px)}
.check-item svg{flex-shrink:0;color:var(--primary)}
.next-card{border-radius:2rem;border:1px solid rgba(255,255,255,0.7);background:rgba(255,255,255,0.4);padding:1.25rem;box-shadow:inset 0 1px 0 rgba(255,255,255,.95);backdrop-filter:blur(24px)}
.next-label{font-size:.75rem;font-weight:600;letter-spacing:.2em;text-transform:uppercase;color:var(--subtle);margin-bottom:1rem}
.next-steps{display:flex;flex-direction:column;gap:1rem}
.next-step{display:flex;align-items:center;gap:.75rem}
.step-num{width:2rem;height:2rem;border-radius:50%;background:var(--green-light);display:flex;align-items:center;justify-content:center;font-size:.75rem;font-weight:700;color:var(--primary);flex-shrink:0}
.step-text{font-size:.875rem;font-weight:500;color:var(--muted)}

/* FORM CARD */
.form-card{border-radius:2.5rem;border:1px solid rgba(255,255,255,0.8);background:rgba(255,255,255,0.54);padding:1.5rem;box-shadow:inset 0 1px 0 #fff,0 24px 75px rgba(17,24,39,0.12);backdrop-filter:blur(34px)}
.form-header{margin-bottom:1.5rem}
.form-community{font-size:.75rem;font-weight:700;letter-spacing:.1em;text-transform:uppercase;color:var(--primary);margin-bottom:.25rem}
.form-title{font-size:1.75rem;font-weight:600;letter-spacing:-.04em;margin-bottom:.5rem}
.form-desc{font-size:.875rem;line-height:1.5;color:var(--subtle)}
.form-fields{display:flex;flex-direction:column;gap:1.25rem}
.field-row{display:grid;gap:1rem}
@media(min-width:768px){.field-row{grid-template-columns:1fr 1fr}}
.field label{display:block}
.field-label{display:block;font-size:.875rem;font-weight:600;color:var(--muted);margin-bottom:.5rem}
.field input[type=text],.field input[type=email],.field textarea{width:100%;border:1px solid var(--border);background:rgba(255,255,255,0.7);border-radius:1rem;padding:.75rem 1rem;font-size:.875rem;outline:none;transition:box-shadow .15s;min-height:3rem}
.field input:focus,.field textarea:focus{box-shadow:0 0 0 4px rgba(20,60,50,0.15)}
.field textarea{min-height:7rem;resize:vertical}
.field-hint{font-size:.75rem;color:var(--subtle);margin-top:.375rem;line-height:1.5}
.bio-count{float:right}
.check-grid{display:grid;gap:.75rem}
@media(min-width:768px){.check-grid{grid-template-columns:1fr 1fr}}
.check-pill{display:flex;align-items:center;gap:.75rem;border:1px solid var(--border);background:rgba(255,255,255,0.58);border-radius:1rem;padding:.75rem 1rem;font-size:.875rem;font-weight:500;color:var(--muted);cursor:pointer;box-shadow:inset 0 1px 0 rgba(255,255,255,.85);min-height:3rem;transition:background .15s}
.check-pill:hover{background:rgba(255,255,255,0.75)}
.check-pill input{accent-color:var(--primary);width:1rem;height:1rem;flex-shrink:0}
.radio-grid-3{display:grid;gap:.75rem}
@media(min-width:768px){.radio-grid-3{grid-template-columns:1fr 1fr 1fr}}
.radio-pill{display:flex;align-items:center;justify-content:center;gap:.5rem;border:1px solid var(--border);background:rgba(255,255,255,0.58);border-radius:1rem;padding:.75rem 1rem;font-size:.875rem;font-weight:600;color:var(--muted);cursor:pointer;box-shadow:inset 0 1px 0 rgba(255,255,255,.85);min-height:3rem;transition:background .15s}
.radio-pill:hover{background:rgba(255,255,255,0.75)}
.radio-pill input{accent-color:var(--primary);width:1rem;height:1rem}
.consent-row{display:flex;align-items:flex-start;gap:.75rem;border:1px solid var(--border);background:rgba(255,255,255,0.48);border-radius:1rem;padding:1rem;font-size:.875rem;line-height:1.5;color:var(--subtle)}
.consent-row input{accent-color:var(--primary);width:1rem;height:1rem;flex-shrink:0;margin-top:.125rem}
.btn-primary{display:flex;align-items:center;justify-content:center;gap:.5rem;width:100%;background:var(--primary);color:#fff;border:none;border-radius:100px;padding:1rem 1.75rem;font-size:1rem;font-weight:600;cursor:pointer;box-shadow:0 18px 40px rgba(20,60,50,0.24);transition:background .15s;min-height:3.375rem}
.btn-primary:hover{background:var(--primary-dk)}
.btn-primary:disabled{opacity:.6;cursor:not-allowed}
.field-error{color:#c0392b;font-size:.8rem;margin-top:.25rem}
.form-error-banner{background:rgba(192,57,43,0.08);border:1px solid rgba(192,57,43,0.2);border-radius:.75rem;padding:.75rem 1rem;font-size:.875rem;color:#c0392b;margin-bottom:1rem}

/* SUCCESS SCREEN */
.success-screen{display:none;position:relative;min-height:38rem;align-items:center;justify-content:center;padding:2rem 0}
.success-screen.show{display:flex}
.success-card{width:100%;max-width:42rem;border-radius:2.5rem;border:1px solid rgba(255,255,255,0.8);background:rgba(255,255,255,0.58);padding:3rem 2rem;text-align:center;box-shadow:inset 0 1px 0 #fff,0 24px 75px rgba(17,24,39,0.12);backdrop-filter:blur(34px)}
@media(min-width:768px){.success-card{padding:4rem 3rem}}
.success-icon{width:5rem;height:5rem;border-radius:50%;background:var(--green-light);display:flex;align-items:center;justify-content:center;margin:0 auto 2rem;box-shadow:inset 0 1px 0 rgba(255,255,255,.9)}
.success-icon svg{width:2.5rem;height:2.5rem;color:var(--primary)}
.success-tag{font-size:.75rem;font-weight:700;letter-spacing:.22em;text-transform:uppercase;color:var(--primary);margin-bottom:.75rem}
.success-h2{font-size:2rem;font-weight:600;letter-spacing:-.045em;line-height:1.1;margin-bottom:1.25rem}
@media(min-width:768px){.success-h2{font-size:2.5rem}}
.success-p{font-size:1rem;line-height:2;color:#3f4338;max-width:32rem;margin:0 auto 2rem}
.expect-card{max-width:28rem;margin:0 auto 2rem;border:1px solid var(--border);background:rgba(255,255,255,0.55);border-radius:2rem;padding:1.25rem;text-align:left;box-shadow:inset 0 1px 0 rgba(255,255,255,.95)}
.expect-inner{display:flex;align-items:flex-start;gap:.75rem}
.expect-inner svg{flex-shrink:0;color:var(--primary);margin-top:.125rem}
.expect-title{font-size:.875rem;font-weight:600;margin-bottom:.25rem}
.expect-text{font-size:.875rem;line-height:1.5;color:var(--subtle)}
.success-actions{display:flex;flex-direction:column;gap:.75rem;justify-content:center;align-items:center}
@media(min-width:480px){.success-actions{flex-direction:row}}
.btn-done{background:var(--primary);color:#fff;border:none;border-radius:100px;padding:.875rem 1.75rem;font-size:1rem;font-weight:600;cursor:pointer;box-shadow:0 18px 40px rgba(20,60,50,0.24);transition:background .15s;min-height:3.25rem}
.btn-done:hover{background:var(--primary-dk)}
.btn-outline{background:rgba(255,255,255,0.7);color:var(--text);border:1px solid var(--border);border-radius:100px;padding:.875rem 1.75rem;font-size:1rem;font-weight:600;cursor:pointer;transition:background .15s;min-height:3.25rem}
.btn-outline:hover{background:#fff}

/* HEADER */
header{position:relative;z-index:20;max-width:80rem;margin:0 auto;padding:1.75rem 1.25rem;display:flex;align-items:center;justify-content:space-between}
@media(min-width:1024px){header{padding:1.75rem 2rem}}
.logo{display:flex;align-items:center;gap:.75rem;border:1px solid var(--border);background:rgba(255,255,255,0.45);border-radius:100px;padding:.5rem 1rem;font-weight:600;font-size:1.0625rem;letter-spacing:-.01em;box-shadow:inset 0 1px 0 rgba(255,255,255,.85),0 16px 45px rgba(0,0,0,.08);backdrop-filter:blur(24px)}
.logo svg{width:1.125rem;height:1.125rem}
nav{display:none;align-items:center;gap:2rem;font-size:.875rem;font-weight:600}
@media(min-width:768px){nav{display:flex}}
nav a{opacity:.75;transition:opacity .15s}
nav a:hover{opacity:1}

/* HERO */
.hero{position:relative;min-height:47rem;overflow:hidden}
@media(min-width:1024px){.hero{min-height:52rem}}
.hero-bg{position:absolute;inset:0;background-image:url('/static/hero-bg.jpg');background-size:cover;background-position:center 30%;background-repeat:no-repeat}
.hero-bg::after{content:'';position:absolute;inset:0;background:linear-gradient(to right,rgba(245,237,227,0.52) 0%,rgba(245,237,227,0.22) 50%,rgba(245,237,227,0.0) 100%)}
.hero-panel{position:absolute;left:52%;top:13%;width:38rem;height:32rem;transform:rotate(-6deg);border-radius:4rem;border:1px solid rgba(255,255,255,0.7);background:rgba(255,255,255,0.25);backdrop-filter:blur(12px);box-shadow:inset 0 1px 0 rgba(255,255,255,.9),0 40px 100px rgba(0,0,0,.16);display:none}
@media(min-width:1024px){.hero-panel{display:block}}
.hero-overlay1{position:absolute;inset:0;background:linear-gradient(to right,rgba(247,241,232,0.78),rgba(247,241,232,0.42),rgba(247,241,232,0.1))}
.hero-overlay2{position:absolute;inset:0;background:linear-gradient(to bottom,rgba(255,255,255,0.2),rgba(255,255,255,0.05),var(--bg))}
.hero-inner{position:relative;z-index:10;max-width:80rem;margin:0 auto;display:grid;gap:2.5rem;padding:2.5rem 1.25rem 6rem;align-items:center}
@media(min-width:1024px){.hero-inner{grid-template-columns:.95fr 1.05fr;padding:4rem 2rem 8rem}}
.hero-text{max-width:48rem;animation:fadeUp .7s ease both}
.hero-eyebrow{font-size:.75rem;font-weight:700;letter-spacing:.24em;text-transform:uppercase;color:var(--primary);margin-bottom:1.5rem}
.hero-h1{font-size:3rem;font-weight:600;line-height:.98;letter-spacing:-.055em;margin-bottom:1.5rem}
@media(min-width:640px){.hero-h1{font-size:3.5rem}}
@media(min-width:1024px){.hero-h1{font-size:4.25rem}}
.hero-h1 em{font-style:italic;color:#27604f}
.hero-p{font-size:1.0625rem;line-height:2;color:var(--muted);max-width:36rem;margin-bottom:2rem}
@media(min-width:768px){.hero-p{font-size:1.25rem}}
.hero-cta{margin-bottom:1.75rem}
.btn-hero{display:inline-flex;align-items:center;gap:.5rem;background:var(--primary);color:#fff;border:none;border-radius:100px;padding:.875rem 1.75rem;font-size:1rem;font-weight:600;cursor:pointer;box-shadow:0 18px 40px rgba(20,60,50,0.28);transition:background .15s;min-height:3.25rem}
.btn-hero:hover{background:var(--primary-dk)}
.hero-pills{display:flex;flex-wrap:wrap;gap:.75rem;list-style:none}
.pill{display:flex;align-items:center;gap:.5rem;border:1px solid var(--border);background:rgba(255,255,255,0.55);border-radius:100px;padding:.5rem 1rem;font-size:.875rem;font-weight:600;color:var(--muted);backdrop-filter:blur(24px);box-shadow:inset 0 1px 0 rgba(255,255,255,.85)}
.pill svg{width:1rem;height:1rem;color:var(--primary)}

/* PHONE MOCKUP */
.phone-wrap{position:relative;max-width:24rem;margin:0 auto;animation:fadeUpRotate .85s ease both}
@media(min-width:1024px){.phone-wrap{max-width:26rem}}
.phone-glow{position:absolute;inset:-2rem;border-radius:3rem;background:rgba(255,255,255,0.25);filter:blur(2rem);pointer-events:none}
.phone-outer{position:relative;border-radius:3.2rem;border:1px solid rgba(255,255,255,0.8);background:rgba(255,255,255,0.18);padding:.75rem;box-shadow:inset 0 1px 0 #fff,inset 0 -30px 80px rgba(255,255,255,.18),0 42px 110px rgba(17,24,39,0.24);backdrop-filter:blur(36px)}
.phone-inner{border-radius:2.65rem;border:1px solid rgba(255,255,255,0.8);background:rgba(251,248,243,0.5);padding:1.25rem;box-shadow:inset 0 1px 0 #fff,inset 0 -24px 60px rgba(255,255,255,.2);backdrop-filter:blur(32px);min-height:37rem}
.phone-bar{display:flex;align-items:center;justify-content:space-between;margin-bottom:1.25rem}
.phone-logo{display:flex;align-items:center;gap:.5rem;font-weight:600;font-size:.9375rem}
.phone-logo svg,.phone-mail svg{width:1.125rem;height:1.125rem}
.email-card{border-radius:2rem;border:1px solid rgba(255,255,255,.7);background:rgba(255,255,255,0.48);padding:1.25rem;box-shadow:inset 0 1px 0 #fff,0 18px 50px rgba(20,60,50,0.08);backdrop-filter:blur(28px)}
.email-hi{font-size:1.375rem;font-weight:600;letter-spacing:-.01em;margin-bottom:.5rem}
.email-intro{font-size:.875rem;line-height:1.5;color:#3f4338;margin-bottom:1.75rem}
.neighbor-card{border-radius:1.55rem;border:1px solid rgba(255,255,255,.6);background:rgba(255,255,255,0.42);padding:1rem;box-shadow:inset 0 1px 0 rgba(255,255,255,.9);backdrop-filter:blur(24px);margin-bottom:1.5rem}
.neighbor-inner{display:flex;align-items:center;gap:1rem}
.avatar{width:4rem;height:4rem;border-radius:50%;background:#d9eee5;display:flex;align-items:center;justify-content:center;font-size:1.25rem;font-weight:600;color:var(--primary);flex-shrink:0}
.neighbor-name{font-size:1.125rem;font-weight:600;margin-bottom:.5rem}
.neighbor-tags{font-size:.8125rem;color:#3f4338;line-height:1.6}
.meeting-tag{border-radius:1.4rem;background:var(--green-light);padding:.75rem 1rem;margin-bottom:1.75rem}
.meeting-tag p{font-size:.875rem;font-weight:600;color:var(--primary);margin-bottom:.125rem}
.meeting-tag span{font-size:.8125rem;color:#3f4338}
.email-btns{display:grid;grid-template-columns:1fr 1fr;gap:.75rem}
.btn-accept{background:var(--primary);color:#fff;border:none;border-radius:1rem;padding:.875rem;font-size:.875rem;font-weight:600;cursor:pointer;min-height:3rem}
.btn-decline{background:rgba(255,255,255,0.7);color:var(--text);border:1px solid var(--border);border-radius:1rem;padding:.875rem;font-size:.875rem;font-weight:600;cursor:pointer;min-height:3rem}

/* STATS */
.stats-section{position:relative;z-index:20;max-width:72rem;margin:-6rem auto 0;padding:0 1.25rem}
@media(min-width:1024px){.stats-section{padding:0 2rem}}
.stats-grid{display:grid;overflow:hidden;border-radius:2.4rem;border:1px solid rgba(255,255,255,0.75);background:rgba(255,255,255,0.38);box-shadow:inset 0 1px 0 #fff,inset 0 -24px 65px rgba(255,255,255,.16),0 24px 75px rgba(17,24,39,0.14);backdrop-filter:blur(34px)}
@media(min-width:768px){.stats-grid{grid-template-columns:repeat(3,1fr)}}
.stat-item{display:flex;align-items:center;gap:1.25rem;padding:1.5rem}
.stat-item+.stat-item{border-top:1px solid var(--border)}
@media(min-width:768px){.stat-item+.stat-item{border-top:none;border-left:1px solid var(--border)}}
.stat-icon{width:3.5rem;height:3.5rem;border-radius:50%;background:var(--green-light);display:flex;align-items:center;justify-content:center;color:var(--primary);flex-shrink:0}
.stat-icon svg{width:1.375rem;height:1.375rem}
.stat-value{font-size:1.875rem;font-weight:600;letter-spacing:-.04em}
.stat-label{font-size:.875rem;font-weight:500;line-height:1.4;color:#3f4338;margin-top:.25rem}

/* HOW IT WORKS */
.how-section{max-width:72rem;margin:0 auto;padding:6rem 1.25rem}
@media(min-width:1024px){.how-section{padding:6rem 2rem}}
.section-eyebrow{font-size:.75rem;font-weight:700;letter-spacing:.22em;text-transform:uppercase;color:var(--subtle);margin-bottom:.75rem;text-align:center}
.section-h2{font-size:2.25rem;font-weight:600;letter-spacing:-.045em;text-align:center;margin-bottom:2.25rem}
@media(min-width:768px){.section-h2{font-size:3rem}}
.steps-grid{display:grid;gap:1rem}
@media(min-width:768px){.steps-grid{grid-template-columns:repeat(3,1fr)}}
.step-card{border-radius:2rem;border:1px solid var(--border);background:rgba(255,255,255,0.46);padding:1.75rem;box-shadow:inset 0 1px 0 rgba(255,255,255,.85),0 18px 50px rgba(17,24,39,0.06);backdrop-filter:blur(24px);animation:fadeUp .55s ease both}
.step-num-badge{width:3.25rem;height:3.25rem;border-radius:50%;background:var(--green-light);display:flex;align-items:center;justify-content:center;font-size:.875rem;font-weight:700;color:var(--primary);margin-bottom:2.25rem}
.step-card h3{font-size:1.375rem;font-weight:600;letter-spacing:-.01em;margin-bottom:.75rem}
.step-card p{font-size:1rem;line-height:1.75;color:#3f4338}

/* COMFORT */
.comfort-section{max-width:72rem;margin:0 auto;padding:0 1.25rem 5rem}
@media(min-width:1024px){.comfort-section{padding:0 2rem 5rem}}
.comfort-card{border-radius:2.5rem;background:var(--primary);padding:1.5rem;color:#fff;box-shadow:0 26px 80px rgba(20,60,50,0.22);animation:fadeUp .55s ease both}
@media(min-width:768px){.comfort-card{padding:2rem}}
.comfort-grid{display:grid;gap:1rem}
@media(min-width:768px){.comfort-grid{grid-template-columns:repeat(4,1fr)}}
.comfort-item{padding:1rem}
.comfort-item+.comfort-item{border-top:1px solid rgba(255,255,255,0.15)}
@media(min-width:768px){.comfort-item+.comfort-item{border-top:none;border-left:1px solid rgba(255,255,255,0.15)}}
.comfort-icon{width:1.5rem;height:1.5rem;opacity:.85;margin-bottom:1rem}
.comfort-item h3{font-size:1rem;font-weight:600;line-height:1.5;margin-bottom:.5rem}
.comfort-item p{font-size:.875rem;line-height:1.5;color:rgba(255,255,255,0.72)}

/* CTA SECTION */
.cta-section{max-width:72rem;margin:0 auto;padding:0 1.25rem 5rem}
@media(min-width:1024px){.cta-section{padding:0 2rem 5rem}}
.cta-card{position:relative;overflow:hidden;border-radius:2.7rem;border:1px solid rgba(255,255,255,0.65);background:rgba(255,255,255,0.5);padding:2rem;box-shadow:inset 0 1px 0 rgba(255,255,255,.95),0 28px 85px rgba(17,24,39,0.1);backdrop-filter:blur(24px);animation:fadeUp .55s ease both}
@media(min-width:768px){.cta-card{padding:2.5rem}}
.cta-card::before{content:'';position:absolute;inset:0;background:radial-gradient(circle at 90% 30%,rgba(216,238,229,0.9),transparent 34%),radial-gradient(circle at 15% 80%,rgba(234,214,189,0.85),transparent 38%);pointer-events:none}
.cta-inner{position:relative;display:grid;gap:2rem;align-items:center}
@media(min-width:1024px){.cta-inner{grid-template-columns:1fr auto}}
.cta-h2{font-size:2.25rem;font-weight:600;line-height:1;letter-spacing:-.045em;margin-bottom:1rem}
@media(min-width:768px){.cta-h2{font-size:3rem}}
.cta-p{font-size:1.0625rem;line-height:2;color:#3f4338}

/* FOOTER */
footer{max-width:72rem;margin:0 auto;padding:0 1.25rem 2.5rem;display:flex;flex-direction:column;gap:.75rem;font-size:.875rem;color:var(--subtle)}
@media(min-width:768px){footer{flex-direction:row;align-items:center;justify-content:space-between}}
@media(min-width:1024px){footer{padding:0 2rem 2.5rem}}
.footer-logo{display:flex;align-items:center;gap:.5rem;font-weight:600;color:var(--text)}
.footer-logo svg{width:1rem;height:1rem}

/* ANIMATIONS */
@keyframes fadeUp{from{opacity:0;transform:translateY(24px)}to{opacity:1;transform:translateY(0)}}
@keyframes fadeUpRotate{from{opacity:0;transform:translateY(24px) rotate(1.5deg) scale(0.96)}to{opacity:1;transform:translateY(0) rotate(-2deg) scale(1)}}
.fade-in{opacity:0;transform:translateY(18px);transition:opacity .55s ease,transform .55s ease}
.fade-in.visible{opacity:1;transform:none}
</style>
</head>
<body>

<!-- MODAL OVERLAY -->
<div id="modal" class="modal" role="dialog" aria-modal="true" aria-label="Join Community Coffee">
  <div class="modal-inner">
    <div class="modal-bar">
      <button class="btn-back" onclick="closeModal()">← Back to page</button>
      <div class="modal-brand">
        <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M10 2v2"/><path d="M14 2v2"/><path d="M16 8a1 1 0 0 1 1 1v8a4 4 0 0 1-4 4H7a4 4 0 0 1-4-4V9a1 1 0 0 1 1-1h14"/><path d="M6 2v2"/><path d="M18 9h2a2 2 0 0 1 0 4h-2"/></svg>
        {{ community_name }}
      </div>
    </div>

    <div class="modal-card">
      <!-- FORM VIEW -->
      <div id="form-view">
        <div class="modal-grid">
          <div class="modal-left">
            <p class="modal-tag">Join once · 60 seconds</p>
            <h1 class="modal-h1">Get your first Monday match.</h1>
            <p class="modal-sub">Tell us a little about you, how you prefer to meet, and who you feel comfortable being introduced to.</p>
            <div class="check-list">
              <div class="check-item"><svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><path d="m9 12 2 2 4-4"/></svg>No app download</div>
              <div class="check-item"><svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><path d="m9 12 2 2 4-4"/></svg>No public resident directory</div>
              <div class="check-item"><svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><path d="m9 12 2 2 4-4"/></svg>You can pause or unsubscribe anytime</div>
            </div>
            <div class="next-card">
              <p class="next-label">What happens next</p>
              <div class="next-steps">
                <div class="next-step"><div class="step-num">1</div><p class="step-text">You submit your profile</p></div>
                <div class="next-step"><div class="step-num">2</div><p class="step-text">We include you in the next Monday match</p></div>
                <div class="next-step"><div class="step-num">3</div><p class="step-text">You accept or decline in one tap</p></div>
              </div>
            </div>
          </div>

          <div class="form-card">
            <div class="form-header">
              <p class="form-community">{{ community_name }}</p>
              <h2 class="form-title">Your matching profile</h2>
              <p class="form-desc">Used only for weekly neighbor introductions.</p>
            </div>

            <div id="form-error" class="form-error-banner" style="display:none"></div>

            <form id="join-form" class="form-fields" novalidate>
              <div class="field-row">
                <div class="field">
                  <label>
                    <span class="field-label">Name or nickname</span>
                    <input type="text" name="full_name" required placeholder="Jane Kim">
                  </label>
                </div>
                <div class="field">
                  <label>
                    <span class="field-label">Email</span>
                    <input type="email" name="email" required placeholder="jane@email.com">
                  </label>
                  <p class="field-hint">Your email stays private — never shown to neighbors.</p>
                </div>
              </div>

              <div class="field">
                <label>
                  <span class="field-label">Short bio <span class="bio-count" id="bio-count" style="font-weight:400;color:var(--subtle)">250 left</span></span>
                  <textarea name="bio" required maxlength="250" rows="3" placeholder="Product designer, amateur baker, always up for a ramen recommendation." oninput="document.getElementById('bio-count').textContent=(250-this.value.length)+' left'"></textarea>
                </label>
                <p class="field-hint">A simple one-liner helps your match say hello.</p>
              </div>

              <div>
                <span class="field-label" style="display:block;margin-bottom:.75rem">Life context <span style="font-weight:400;color:var(--subtle)">(optional)</span></span>
                <div class="check-grid">
                  {% for tag in life_context_options %}
                  <label class="check-pill">
                    <input type="checkbox" name="life_context" value="{{ tag }}">
                    {{ tag }}
                  </label>
                  {% endfor %}
                </div>
              </div>

              <div>
                <span class="field-label" style="display:block;margin-bottom:.75rem">Preferred way to meet</span>
                <div class="check-grid">
                  {% for group in groups %}
                  <label class="check-pill">
                    <input type="radio" name="meet_group" value="{{ group.name }}" required>
                    {{ group.displayName }}
                  </label>
                  {% endfor %}
                </div>
              </div>

              <div>
                <span class="field-label" style="display:block;margin-bottom:.75rem">Who are you comfortable meeting?</span>
                <div class="radio-grid-3">
                  <label class="radio-pill"><input type="radio" name="gender_pref" value="any" checked required> No preference</label>
                  <label class="radio-pill"><input type="radio" name="gender_pref" value="women"> Women only</label>
                  <label class="radio-pill"><input type="radio" name="gender_pref" value="men"> Men only</label>
                </div>
              </div>

              <label class="consent-row">
                <input type="checkbox" name="consent" required>
                I agree to receive weekly Community Coffee introduction emails.
              </label>

              <input type="hidden" name="cadence" value="0">
              <button type="submit" class="btn-primary" id="submit-btn">
                Join the next Monday match
                <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M5 12h14"/><path d="m12 5 7 7-7 7"/></svg>
              </button>
            </form>
          </div>
        </div>
      </div>

      <!-- SUCCESS VIEW -->
      <div id="success-view" class="success-screen">
        <div class="success-card">
          <div class="success-icon">
            <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><path d="m9 12 2 2 4-4"/></svg>
          </div>
          <p class="success-tag">You're in</p>
          <h2 class="success-h2">Invitation confirmed.<br>Check your inbox.</h2>
          <p class="success-p">We'll email you when your next Monday match is ready. Keep an eye on your inbox for your first neighbor introduction.</p>
          <div class="expect-card">
            <div class="expect-inner">
              <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect width="20" height="16" x="2" y="4" rx="2"/><path d="m22 7-8.97 5.7a1.94 1.94 0 0 1-2.06 0L2 7"/></svg>
              <div>
                <p class="expect-title">What to expect</p>
                <p class="expect-text">Your first match will arrive by email. From there, you can accept, decline, or pause anytime.</p>
              </div>
            </div>
          </div>
          <div class="success-actions">
            <button class="btn-done" onclick="closeModal()">Done</button>
            <button class="btn-outline" onclick="editProfile()">Edit my profile</button>
          </div>
        </div>
      </div>
    </div><!-- /modal-card -->
  </div>
</div><!-- /modal -->

<!-- HEADER -->
<header>
  <a href="#main" class="logo" aria-label="Community Coffee home">
    <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M10 2v2"/><path d="M14 2v2"/><path d="M16 8a1 1 0 0 1 1 1v8a4 4 0 0 1-4 4H7a4 4 0 0 1-4-4V9a1 1 0 0 1 1-1h14"/><path d="M6 2v2"/><path d="M18 9h2a2 2 0 0 1 0 4h-2"/></svg>
    Community Coffee
  </a>
  <nav aria-label="Main navigation">
    <a href="#how">How it works</a>
    <a href="#comfort">Comfort</a>
    <a href="#join">Join</a>
  </nav>
</header>

<main id="main">
  <!-- HERO -->
  <section class="hero">
    <div class="hero-bg"></div>
    <div class="hero-panel"></div>
    <div class="hero-overlay1"></div>
    <div class="hero-overlay2"></div>
    <div class="hero-inner">
      <div class="hero-text">
        <p class="hero-eyebrow">One neighbor. Every Monday.</p>
        <h1 class="hero-h1">Feel more at home, <em>one neighbor</em> at a time.</h1>
        <p class="hero-p">Meet nearby residents and make home feel more familiar.</p>
        <div class="hero-cta">
          <button class="btn-hero" onclick="openModal()">
            Join the next Monday match
            <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M5 12h14"/><path d="m12 5 7 7-7 7"/></svg>
          </button>
        </div>
        <ul class="hero-pills">
          <li class="pill"><svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><path d="m9 12 2 2 4-4"/></svg>No app</li>
          <li class="pill"><svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><path d="m9 12 2 2 4-4"/></svg>One tap</li>
          <li class="pill"><svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><path d="m9 12 2 2 4-4"/></svg>Pause anytime</li>
        </ul>
      </div>

      <div class="phone-wrap">
        <div class="phone-glow"></div>
        <div class="phone-outer">
          <div class="phone-inner">
            <div class="phone-bar">
              <div class="phone-logo">
                <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M10 2v2"/><path d="M14 2v2"/><path d="M16 8a1 1 0 0 1 1 1v8a4 4 0 0 1-4 4H7a4 4 0 0 1-4-4V9a1 1 0 0 1 1-1h14"/><path d="M6 2v2"/><path d="M18 9h2a2 2 0 0 1 0 4h-2"/></svg>
                Community Coffee
              </div>
              <div class="phone-mail"><svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect width="20" height="16" x="2" y="4" rx="2"/><path d="m22 7-8.97 5.7a1.94 1.94 0 0 1-2.06 0L2 7"/></svg></div>
            </div>
            <div class="email-card">
              <h2 class="email-hi">Hi Jane,</h2>
              <p class="email-intro">We'd like to introduce you to your neighbor this week.</p>
              <div class="neighbor-card">
                <div class="neighbor-inner">
                  <div class="avatar">M</div>
                  <div>
                    <div class="neighbor-name">Marcus Lee</div>
                    <div class="neighbor-tags">Product designer<br>Amateur baker<br>Works from home</div>
                  </div>
                </div>
              </div>
              <div class="meeting-tag">
                <p>Coffee chat</p>
                <span>15 min nearby</span>
              </div>
              <div class="email-btns">
                <button class="btn-accept">Accept</button>
                <button class="btn-decline">Decline</button>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  </section>

  <!-- STATS -->
  <section class="stats-section" aria-label="Key stats">
    <div class="stats-grid">
      <div class="stat-item">
        <div class="stat-icon"><svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M18 21a8 8 0 0 0-16 0"/><circle cx="10" cy="8" r="5"/><path d="M22 20c0-3.37-2-6.5-4-8a5 5 0 0 0-.45-8.3"/></svg></div>
        <div><p class="stat-value">1</p><p class="stat-label">neighbor introduced each week</p></div>
      </div>
      <div class="stat-item">
        <div class="stat-icon"><svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M10 2v2"/><path d="M14 2v2"/><path d="M16 8a1 1 0 0 1 1 1v8a4 4 0 0 1-4 4H7a4 4 0 0 1-4-4V9a1 1 0 0 1 1-1h14"/><path d="M6 2v2"/><path d="M18 9h2a2 2 0 0 1 0 4h-2"/></svg></div>
        <div><p class="stat-value">15</p><p class="stat-label">minutes is enough to start</p></div>
      </div>
      <div class="stat-item">
        <div class="stat-icon"><svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="16" r="1"/><rect x="3" y="10" width="18" height="12" rx="2"/><path d="M7 10V7a5 5 0 0 1 10 0v3"/></svg></div>
        <div><p class="stat-value">0</p><p class="stat-label">public profiles or directories</p></div>
      </div>
    </div>
  </section>

  <!-- HOW IT WORKS -->
  <section id="how" class="how-section">
    <p class="section-eyebrow">How it works</p>
    <h2 class="section-h2">Three simple steps.</h2>
    <div class="steps-grid">
      <div class="step-card fade-in">
        <div class="step-num-badge">01</div>
        <h3>Scan the QR code</h3>
        <p>Join once with your email and basic preferences.</p>
      </div>
      <div class="step-card fade-in" style="animation-delay:.1s">
        <div class="step-num-badge">02</div>
        <h3>Get a Monday match</h3>
        <p>We send one simple introduction to someone nearby.</p>
      </div>
      <div class="step-card fade-in" style="animation-delay:.2s">
        <div class="step-num-badge">03</div>
        <h3>Say yes or pause</h3>
        <p>Accept, skip, or pause whenever you need.</p>
      </div>
    </div>
  </section>

  <!-- COMFORT -->
  <section id="comfort" class="comfort-section">
    <div class="comfort-card fade-in">
      <div class="comfort-grid">
        <div class="comfort-item">
          <svg class="comfort-icon" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M18 21a8 8 0 0 0-16 0"/><circle cx="10" cy="8" r="5"/><path d="M22 20c0-3.37-2-6.5-4-8a5 5 0 0 0-.45-8.3"/></svg>
          <h3>Choose who feels right</h3>
          <p>Women only, men only, or no preference.</p>
        </div>
        <div class="comfort-item">
          <svg class="comfort-icon" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><line x1="10" x2="10" y1="15" y2="9"/><line x1="14" x2="14" y1="15" y2="9"/></svg>
          <h3>Pause anytime</h3>
          <p>Life happens. You stay in control.</p>
        </div>
        <div class="comfort-item">
          <svg class="comfort-icon" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="16" r="1"/><rect x="3" y="10" width="18" height="12" rx="2"/><path d="M7 10V7a5 5 0 0 1 10 0v3"/></svg>
          <h3>No public directory</h3>
          <p>No public profiles or shared contact details.</p>
        </div>
        <div class="comfort-item">
          <svg class="comfort-icon" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M20 13c0 5-3.5 7.5-7.66 8.95a1 1 0 0 1-.67-.01C7.5 20.5 4 18 4 13V6a1 1 0 0 1 1-1c2 0 4.5-1.2 6.24-2.72a1.17 1.17 0 0 1 1.52 0C14.51 3.81 17 5 19 5a1 1 0 0 1 1 1z"/><path d="m9 12 2 2 4-4"/></svg>
          <h3>Privacy first</h3>
          <p>Email-based matching. Your email stays private, always.</p>
        </div>
      </div>
    </div>
  </section>

  <!-- CTA -->
  <section id="join" class="cta-section">
    <div class="cta-card fade-in">
      <div class="cta-inner">
        <div>
          <h2 class="cta-h2">Your next neighbor could be one Monday away.</h2>
          <p class="cta-p">One match. One easy hello.</p>
        </div>
        <button class="btn-hero" onclick="openModal()">
          Join the next Monday match
          <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M5 12h14"/><path d="m12 5 7 7-7 7"/></svg>
        </button>
      </div>
    </div>
  </section>
</main>

<footer>
  <div class="footer-logo">
    <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M10 2v2"/><path d="M14 2v2"/><path d="M16 8a1 1 0 0 1 1 1v8a4 4 0 0 1-4 4H7a4 4 0 0 1-4-4V9a1 1 0 0 1 1-1h14"/><path d="M6 2v2"/><path d="M18 9h2a2 2 0 0 1 0 4h-2"/></svg>
    Community Coffee
  </div>
  <p>One introduction. One easier way to feel at home.</p>
</footer>

<script>
function openModal(){
  document.getElementById('modal').classList.add('open');
  document.body.style.overflow='hidden';
}
function closeModal(){
  document.getElementById('modal').classList.remove('open');
  document.body.style.overflow='';
  document.getElementById('form-view').style.display='';
  document.getElementById('success-view').classList.remove('show');
}
function editProfile(){
  document.getElementById('form-view').style.display='';
  document.getElementById('success-view').classList.remove('show');
}

document.getElementById('join-form').addEventListener('submit',async function(e){
  e.preventDefault();
  const btn=document.getElementById('submit-btn');
  const errBanner=document.getElementById('form-error');
  btn.disabled=true;btn.textContent='Joining...';
  errBanner.style.display='none';
  try{
    const res=await fetch('/join',{method:'POST',body:new FormData(this)});
    const text=await res.text();
    if(res.ok && (text.includes("You're in") || text.includes("in!"))){
      document.getElementById('form-view').style.display='none';
      document.getElementById('success-view').classList.add('show');
    } else {
      errBanner.textContent='Please fill in all required fields and try again.';
      errBanner.style.display='block';
    }
  }catch(err){
    errBanner.textContent='Something went wrong. Please try again.';
    errBanner.style.display='block';
  }finally{
    btn.disabled=false;btn.innerHTML='Join the next Monday match <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M5 12h14"/><path d="m12 5 7 7-7 7"/></svg>';
  }
});

// Scroll animations
const obs=new IntersectionObserver((entries)=>{
  entries.forEach(e=>{if(e.isIntersecting){e.target.classList.add('visible')}});
},{threshold:0.1});
document.querySelectorAll('.fade-in').forEach(el=>obs.observe(el));

// Close modal on backdrop click
document.getElementById('modal').addEventListener('click',function(e){
  if(e.target===this)closeModal();
});
// Escape key
document.addEventListener('keydown',function(e){if(e.key==='Escape')closeModal()});
</script>
</body>
</html>"""

THANK_YOU_TEMPLATE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>You're in — Community Coffee</title>
<style>
*{box-sizing:border-box;margin:0;padding:0}
body{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;background:#f4efe7;color:#151711;min-height:100vh;display:flex;align-items:center;justify-content:center;padding:2rem 1rem}
.card{width:100%;max-width:38rem;border-radius:2.5rem;border:1px solid rgba(255,255,255,0.8);background:rgba(255,255,255,0.58);padding:3rem 2rem;text-align:center;box-shadow:inset 0 1px 0 #fff,0 24px 75px rgba(17,24,39,0.12);backdrop-filter:blur(34px)}
.icon{width:5rem;height:5rem;border-radius:50%;background:#edf5f0;display:flex;align-items:center;justify-content:center;margin:0 auto 2rem;box-shadow:inset 0 1px 0 rgba(255,255,255,.9)}
.icon svg{width:2.5rem;height:2.5rem;color:#143c32}
.tag{font-size:.75rem;font-weight:700;letter-spacing:.22em;text-transform:uppercase;color:#143c32;margin-bottom:.75rem}
h1{font-size:2rem;font-weight:600;letter-spacing:-.045em;line-height:1.1;margin-bottom:1.25rem}
p{font-size:1rem;line-height:2;color:#3f4338;max-width:30rem;margin:0 auto 2rem}
.expect{max-width:26rem;margin:0 auto 2rem;border:1px solid rgba(21,23,17,0.1);background:rgba(255,255,255,0.55);border-radius:2rem;padding:1.25rem;text-align:left}
.expect-row{display:flex;align-items:flex-start;gap:.75rem}
.expect-row svg{flex-shrink:0;color:#143c32;margin-top:.125rem;width:1.25rem;height:1.25rem}
.expect-title{font-size:.875rem;font-weight:600;margin-bottom:.25rem}
.expect-text{font-size:.875rem;line-height:1.5;color:#5e6459}
a.btn{display:inline-block;background:#143c32;color:#fff;border-radius:100px;padding:.875rem 1.75rem;font-size:1rem;font-weight:600;text-decoration:none;box-shadow:0 18px 40px rgba(20,60,50,0.24)}
</style>
</head>
<body>
<div class="card">
  <div class="icon">
    <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><path d="m9 12 2 2 4-4"/></svg>
  </div>
  <p class="tag">You're in</p>
  <h1>Invitation confirmed.<br>Check your inbox.</h1>
  <p>We'll email you when your next Monday match is ready. Every Monday, one neighbor intro.</p>
  <div class="expect">
    <div class="expect-row">
      <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect width="20" height="16" x="2" y="4" rx="2"/><path d="m22 7-8.97 5.7a1.94 1.94 0 0 1-2.06 0L2 7"/></svg>
      <div>
        <p class="expect-title">What to expect</p>
        <p class="expect-text">Your first match will arrive by email. From there, you can accept, decline, or pause anytime.</p>
      </div>
    </div>
  </div>
  <a href="/" class="btn">Done</a>
</div>
</body>
</html>"""

ADMIN_TEMPLATE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Admin — Community Coffee</title>
<style>
*{box-sizing:border-box;margin:0;padding:0}
body{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;background:#f0f2f0;color:#151711;min-height:100vh}
.topbar{background:#143c32;color:#fff;padding:.875rem 1.5rem;display:flex;align-items:center;justify-content:space-between}
.topbar-logo{display:flex;align-items:center;gap:.625rem;font-weight:600;font-size:.9375rem}
.topbar-logo svg{width:1.125rem;height:1.125rem;opacity:.9}
.topbar-right{font-size:.8125rem;opacity:.7}
.wrap{max-width:80rem;margin:0 auto;padding:1.5rem 1.25rem}
@media(min-width:768px){.wrap{padding:2rem 2rem}}
.page-title{font-size:1.5rem;font-weight:700;letter-spacing:-.02em;margin-bottom:.25rem}
.page-sub{font-size:.875rem;color:#5e6459;margin-bottom:2rem}
.grid-3{display:grid;gap:1rem;margin-bottom:2rem}
@media(min-width:768px){.grid-3{grid-template-columns:repeat(3,1fr)}}
.metric-card{background:#fff;border-radius:1.25rem;padding:1.25rem 1.5rem;box-shadow:0 1px 3px rgba(0,0,0,.06),0 4px 12px rgba(0,0,0,.04)}
.metric-label{font-size:.75rem;font-weight:600;letter-spacing:.08em;text-transform:uppercase;color:#5e6459;margin-bottom:.5rem}
.metric-value{font-size:2rem;font-weight:700;letter-spacing:-.04em;color:#143c32}
.section-card{background:#fff;border-radius:1.25rem;padding:1.5rem;box-shadow:0 1px 3px rgba(0,0,0,.06),0 4px 12px rgba(0,0,0,.04);margin-bottom:1.5rem}
.section-header{display:flex;align-items:center;justify-content:space-between;margin-bottom:1.25rem;flex-wrap:wrap;gap:.75rem}
.section-title{font-size:1rem;font-weight:700;letter-spacing:-.01em}
.btn-action{display:inline-flex;align-items:center;gap:.375rem;background:#143c32;color:#fff;border:none;border-radius:.625rem;padding:.5rem 1rem;font-size:.8125rem;font-weight:600;cursor:pointer;transition:background .15s;text-decoration:none}
.btn-action:hover{background:#0f2f28}
.btn-secondary{background:transparent;color:#143c32;border:1px solid #143c32}
.btn-secondary:hover{background:#edf5f0}
.table-wrap{overflow-x:auto;-webkit-overflow-scrolling:touch}
table{width:100%;border-collapse:collapse;font-size:.8125rem}
th{text-align:left;padding:.625rem .75rem;font-weight:600;font-size:.75rem;letter-spacing:.06em;text-transform:uppercase;color:#5e6459;border-bottom:1px solid #e8ebe8;white-space:nowrap}
td{padding:.75rem .75rem;border-bottom:1px solid #f0f2f0;vertical-align:top;max-width:16rem}
tr:last-child td{border-bottom:none}
tr:hover td{background:#fafbfa}
.badge{display:inline-block;padding:.2rem .625rem;border-radius:100px;font-size:.6875rem;font-weight:600;background:#edf5f0;color:#143c32}
.empty{text-align:center;padding:3rem 1rem;color:#5e6459;font-size:.875rem}
.actions-grid{display:grid;gap:1rem}
@media(min-width:640px){.actions-grid{grid-template-columns:1fr 1fr}}
.action-block{border:1px solid #e8ebe8;border-radius:1rem;padding:1.25rem}
.action-title{font-size:.875rem;font-weight:700;margin-bottom:.375rem}
.action-desc{font-size:.8125rem;color:#5e6459;line-height:1.5;margin-bottom:1rem}
.action-form{display:flex;gap:.5rem;flex-wrap:wrap;align-items:flex-end}
.action-form input[type=email]{border:1px solid #d0d4d0;border-radius:.625rem;padding:.5rem .75rem;font-size:.875rem;outline:none;flex:1;min-width:0}
.action-form input:focus{box-shadow:0 0 0 3px rgba(20,60,50,0.12)}
.alert{padding:.875rem 1rem;border-radius:.75rem;font-size:.875rem;font-weight:500;margin-bottom:1.5rem}
.alert-success{background:#edf5f0;color:#143c32;border:1px solid rgba(20,60,50,0.15)}
.alert-error{background:#fdf0ef;color:#c0392b;border:1px solid rgba(192,57,43,0.15)}
.truncate{overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
</style>
</head>
<body>
<div class="topbar">
  <div class="topbar-logo">
    <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M10 2v2"/><path d="M14 2v2"/><path d="M16 8a1 1 0 0 1 1 1v8a4 4 0 0 1-4 4H7a4 4 0 0 1-4-4V9a1 1 0 0 1 1-1h14"/><path d="M6 2v2"/><path d="M18 9h2a2 2 0 0 1 0 4h-2"/></svg>
    Community Coffee — Admin
  </div>
  <div class="topbar-right">{{ community_name }}</div>
</div>

<div class="wrap">
  <div class="page-title">Dashboard</div>
  <div class="page-sub">Manage participants, trigger matching, and preview emails.</div>

  {% if message %}
  <div class="alert alert-success">{{ message }}</div>
  {% endif %}

  <!-- METRICS -->
  <div class="grid-3">
    <div class="metric-card">
      <div class="metric-label">Total participants</div>
      <div class="metric-value">{{ users|length }}</div>
    </div>
    <div class="metric-card">
      <div class="metric-label">Active (weekly)</div>
      <div class="metric-value">{{ users|selectattr('pause_in_weeks','eq','0')|list|length }}</div>
    </div>
    <div class="metric-card">
      <div class="metric-label">Community</div>
      <div class="metric-value" style="font-size:1.125rem;margin-top:.25rem">{{ community_name }}</div>
    </div>
  </div>

  <!-- ACTIONS -->
  <div class="section-card">
    <div class="section-title" style="margin-bottom:1rem">Actions</div>
    <div class="actions-grid">
      <div class="action-block">
        <div class="action-title">Run matching</div>
        <div class="action-desc">Manually trigger this week's neighbor pairings. Matched pairs receive an intro email immediately.</div>
        <form method="post" action="/admin/matches?token={{ token }}">
          <button type="submit" class="btn-action">Run matching now</button>
        </form>
      </div>
      <div class="action-block">
        <div class="action-title">Send test email</div>
        <div class="action-desc">Preview exactly what residents will receive — a sample intro with Marcus Lee as the match.</div>
        <form class="action-form" method="get" action="/admin/test-email">
          <input type="hidden" name="token" value="{{ token }}">
          <input type="email" name="to" required placeholder="your@email.com">
          <button type="submit" class="btn-action">Send</button>
        </form>
      </div>
    </div>
    <div style="margin-top:1rem;padding-top:1rem;border-top:1px solid #e8ebe8">
      <a href="/admin/matches?token={{ token }}&format=csv" class="btn-action btn-secondary">Download matches CSV</a>
    </div>
  </div>

  <!-- PARTICIPANTS TABLE -->
  <div class="section-card">
    <div class="section-header">
      <div class="section-title">Participants</div>
      <span style="font-size:.8125rem;color:#5e6459">{{ users|length }} total</span>
    </div>
    {% if users %}
    <div class="table-wrap">
      <table>
        <thead>
          <tr>
            <th>Name</th>
            <th>Email</th>
            <th>Activity</th>
            <th>Gender</th>
            <th>Bio</th>
            <th>Life context</th>
            <th>Cadence</th>
            <th>Joined</th>
          </tr>
        </thead>
        <tbody>
          {% for u in users %}
          <tr>
            <td style="font-weight:600">{{ u.full_name or u.username }}</td>
            <td style="color:#5e6459" class="truncate">{{ u.email }}</td>
            <td><span class="badge">{{ activity_labels.get(u.meet_group, u.meet_group) }}</span></td>
            <td style="color:#5e6459">{{ u.gender_pref or '—' }}</td>
            <td style="color:#5e6459;max-width:12rem" class="truncate">{{ u.bio or '—' }}</td>
            <td style="color:#5e6459">{{ u.extra_info or '—' }}</td>
            <td><span class="badge" style="background:{% if u.pause_in_weeks == '0' %}#edf5f0{% else %}#fdf6ed{% endif %};color:{% if u.pause_in_weeks == '0' %}#143c32{% else %}#b7590a{% endif %}">{{ 'Weekly' if u.pause_in_weeks == '0' else 'Paused ' + u.pause_in_weeks + 'w' }}</span></td>
            <td style="color:#5e6459;white-space:nowrap">{{ u.tmst_created.strftime('%b %d, %Y') if u.tmst_created else '—' }}</td>
          </tr>
          {% endfor %}
        </tbody>
      </table>
    </div>
    {% else %}
    <div class="empty">No participants yet. Share the signup link to get started.</div>
    {% endif %}
  </div>
</div>
</body>
</html>"""


def _matches_to_csv(rows):
    if not rows:
        return ""
    headers = rows[0].keys()
    out = io.StringIO()
    writer = csv.DictWriter(out, fieldnames=headers)
    writer.writeheader()
    for row in rows:
        writer.writerow(row)
    return out.getvalue()


def _serialize_match(meet):
    try:
        user1 = user_repo.get_by_id(meet.uid1)
        user2 = user_repo.get_by_id(meet.uid2)
    except UserNotFoundError:
        return None

    return {
        "meet_id": meet.id,
        "season": meet.season,
        "status": meet.status,
        "proposal_sent": meet.proposal_sent,
        "uid1": user1.id,
        "email1": user1.email,
        "name1": user1.full_name or user1.username,
        "uid2": user2.id,
        "email2": user2.email,
        "name2": user2.full_name or user2.username,
        "activity": user1.meet_group or user2.meet_group,
    }


def _check_admin():
    """Admin auth for the panel AND the weekly cron (POST /admin/matches).

    Accepts `Authorization: Bearer <token>` (preferred — used by the cron)
    or `?token=` (browser convenience). Constant-time compare so the token
    can't be guessed byte-by-byte from response timing.
    """
    token = request.headers.get("Authorization", "")
    if token.startswith("Bearer "):
        token = token.split(" ", 1)[1]
    if not token:
        token = request.args.get("token", "")
    admin_token = app.config.get("ADMIN_TOKEN")
    if not admin_token or not token:
        return False
    return hmac.compare_digest(token, admin_token)


@app.route("/", methods=["GET"])
def home():
    groups = config["community"].get("enabledGroups", [])
    community_name = config["community"].get("displayName", "Community")
    return render_template_string(
        HOME_TEMPLATE,
        groups=groups,
        community_name=community_name,
        life_context_options=LIFE_CONTEXT_OPTIONS,
        error=None,
    )


@app.route("/join", methods=["POST"])
def join():
    payload = request.get_json(silent=True)
    if payload is None:
        payload = request.form

    email = (payload.get("email") or "").strip().lower()
    full_name = (payload.get("full_name") or "").strip()
    meet_group = (payload.get("meet_group") or "").strip()
    bio = (payload.get("bio") or "").strip()[:250]
    gender_pref = (payload.get("gender_pref") or "any").strip()
    cadence = (payload.get("cadence") or "0").strip()
    if cadence not in ("0", "1", "2", "3", "4"):
        cadence = "0"
    if gender_pref not in ("any", "women", "men"):
        gender_pref = "any"

    # Life context: checkboxes → comma-joined string
    if request.is_json:
        life_context_raw = payload.get("life_context", [])
        if isinstance(life_context_raw, str):
            life_context_raw = [life_context_raw]
    else:
        life_context_raw = request.form.getlist("life_context")
    extra_info = ", ".join(
        tag for tag in life_context_raw if tag in LIFE_CONTEXT_OPTIONS
    )

    def _form_error(msg):
        groups = config["community"].get("enabledGroups", [])
        community_name = config["community"].get("displayName", "Community")
        return render_template_string(
            HOME_TEMPLATE, groups=groups, community_name=community_name,
            life_context_options=LIFE_CONTEXT_OPTIONS, error=msg,
        ), 400

    if not email or not full_name or not meet_group or not bio:
        if request.is_json:
            return jsonify({"error": "email, full_name, meet_group, and bio are required"}), 400
        return _form_error("Please fill in all required fields.")

    permitted_groups = {group["name"] for group in config["community"].get("enabledGroups", [])}
    if meet_group not in permitted_groups:
        if request.is_json:
            return jsonify({"error": "Invalid activity preference"}), 400
        return _form_error("Please select a valid activity preference.")

    if not request.is_json and not payload.get("consent"):
        return _form_error("Please agree to receive match emails to continue.")

    try:
        user = user_repo.get_by_email(email)
        user.full_name = full_name
        user.username = full_name
        user.email = email
        user.meet_group = meet_group
        user.pause_in_weeks = cadence
        user.bio = bio
        user.extra_info = extra_info
        user.gender_pref = gender_pref
        user_repo.update(user)
        created = False
    except UserNotFoundError:
        user = User(
            id=str(uuid.uuid4()),
            username=full_name,
            email=email,
            full_name=full_name,
            loc="community",
            meet_group=meet_group,
            pause_in_weeks=cadence,
            bio=bio,
            extra_info=extra_info,
            gender_pref=gender_pref,
        )
        user_repo.add(user)
        created = True

    # Send confirmation email
    community_name = config["community"].get("displayName", "Community")
    try:
        subject, body, html = emails.confirmation_email(full_name, community_name)
        email_client.send(to_address=email, subject=subject, body=body, html=html)
    except Exception as exc:
        logger.error("Failed to send confirmation email to %s: %s", email, exc)

    if request.is_json:
        return jsonify({"status": "ok", "message": "Profile created" if created else "Profile updated"})

    return render_template_string(THANK_YOU_TEMPLATE, community_name=community_name)


@app.route("/admin", methods=["GET"])
def admin_panel():
    if not _check_admin():
        return Response("Unauthorized", status=401)
    token = request.args.get("token", "")
    message = request.args.get("message", "")
    users = list(user_repo.list())
    community_name = config["community"].get("displayName", "Community")
    return render_template_string(
        ADMIN_TEMPLATE,
        users=users,
        token=token,
        message=message,
        activity_labels=ACTIVITY_LABELS,
        community_name=community_name,
    )


@app.route("/admin/test-email", methods=["GET"])
def admin_test_email():
    if not _check_admin():
        return Response("Unauthorized", status=401)

    to = request.args.get("to", "").strip()
    token = request.args.get("token", "")
    if not to:
        return Response("Missing ?to= parameter", status=400)

    community_name = config["community"].get("displayName", "Community")
    base_url = config["app"].get("baseUrl", "http://localhost:5000").rstrip("/")

    # Same template as real sends — the preview can never drift from reality.
    subject, body, html = emails.match_proposal_email(
        recipient_name="Alex",
        peer_name="Marcus Lee",
        peer_bio="Product designer, amateur baker, always up for a ramen recommendation.",
        peer_activity="coffee",
        peer_extra="Has kids, Works from home, New here",
        accept_url=f"{base_url}/respond?meet_id=1&uid=test&action=accept&signature=test",
        decline_url=f"{base_url}/respond?meet_id=1&uid=test&action=decline&signature=test",
        community_name=community_name,
    )

    try:
        email_client.send(
            to_address=to,
            subject=f"[TEST] {subject}",
            body=body,
            html=html,
        )
        logger.info("Test email sent to %s", to)
        message = f"Test email sent to {to}!"
    except Exception as exc:
        logger.error("Failed to send test email to %s: %s", to, exc)
        message = f"Failed to send: {exc}"

    return render_template_string(
        ADMIN_TEMPLATE,
        users=list(user_repo.list()),
        token=token,
        message=message,
        activity_labels=ACTIVITY_LABELS,
        community_name=community_name,
    )


@app.route("/admin/matches", methods=["GET"])
def list_matches():
    if not _check_admin():
        return jsonify({"error": "Unauthorized"}), 401

    matches = [row for row in (_serialize_match(meet) for meet in meet_repo.list()) if row]
    if request.args.get("format") == "csv":
        csv_data = _matches_to_csv(matches)
        return Response(
            csv_data,
            mimetype="text/csv",
            headers={"Content-Disposition": "attachment; filename=matches.csv"}
        )

    return jsonify(matches)


@app.route("/admin/matches", methods=["POST"])
def trigger_matches():
    if not _check_admin():
        return jsonify({"error": "Unauthorized"}), 401

    force = request.args.get("force", "0").lower() in ("1", "true", "yes")
    result = matching_service.generate_matches(force=force)
    return jsonify(result)


RESPOND_CARD = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title} — Community Coffee</title>
</head>
<body style="margin:0;padding:0;background:#f5ede3;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif">
<div style="min-height:100vh;display:flex;align-items:center;justify-content:center;padding:2rem 1rem">
  <div style="width:100%;max-width:400px;background:#fff;border-radius:24px;padding:3rem 2rem;text-align:center;box-shadow:0 8px 40px rgba(26,31,24,0.1)">
    <div style="width:5rem;height:5rem;border-radius:50%;background:{icon_bg};color:{icon_color};font-size:1.75rem;font-weight:700;display:flex;align-items:center;justify-content:center;margin:0 auto 1.5rem">{icon}</div>
    <p style="font-size:11px;font-weight:700;letter-spacing:2px;text-transform:uppercase;color:#143c32;margin:0 0 8px">{community_name}</p>
    <h1 style="font-size:22px;font-weight:700;color:#1a1f18;margin:0 0 12px;letter-spacing:-0.3px">{headline}</h1>
    <p style="font-size:15px;color:#5a6356;line-height:1.6;margin:0">{message}</p>
    {extra}
    <a href="/" style="display:inline-block;margin-top:2rem;background:#143c32;color:#f5ede3;text-decoration:none;border-radius:100px;padding:0.75rem 1.75rem;font-size:14px;font-weight:600">Back to Community Coffee</a>
  </div>
</div>
</body>
</html>"""


def _respond_page(*, headline, message, icon="✓", icon_bg="#143c32",
                  icon_color="#f5ede3", extra=""):
    community_name = config["community"].get("displayName", "Community Coffee")
    html = RESPOND_CARD.format(
        title=headline, headline=headline, message=message, icon=icon,
        icon_bg=icon_bg, icon_color=icon_color, extra=extra,
        community_name=escape(community_name),
    )
    return Response(html, status=200, mimetype="text/html")


def _peer_card(peer_avatar, peer_name, peer_bio):
    bio_block = (
        f'''<div style="font-size:13px;color:#5a6356;font-style:italic;margin-top:2px">"{peer_bio}"</div>'''
        if peer_bio else ""
    )
    return f"""
        <div style="background:#faf7f2;border:1px solid rgba(26,31,24,0.08);border-radius:16px;padding:18px 20px;margin:24px 0;text-align:left">
          <div style="display:flex;align-items:center;gap:12px">
            <div style="width:44px;height:44px;border-radius:50%;background:#143c32;color:#f5ede3;display:flex;align-items:center;justify-content:center;font-size:18px;font-weight:700;flex-shrink:0">{peer_avatar}</div>
            <div>
              <div style="font-weight:700;font-size:16px;color:#1a1f18">{peer_name}</div>
              {bio_block}
            </div>
          </div>
        </div>"""


def _parse_respond_request(values):
    """Shared validation for GET (confirm) and POST (act). Returns
    (meet_id_str, meet_id_int, uid, action, error_response)."""
    meet_id = values.get("meet_id")
    uid = values.get("uid")
    action = values.get("action")
    signature = values.get("signature")

    if not all([meet_id, uid, action, signature]):
        return None, None, None, None, Response("Missing required parameters", status=400)
    try:
        meet_id_int = int(meet_id)
    except ValueError:
        return None, None, None, None, Response("Invalid meet_id", status=400)
    if not response_service.validate_signature(meet_id, uid, action, signature):
        return None, None, None, None, Response("Invalid token", status=400)
    return meet_id, meet_id_int, uid, action, None


def _peer_display(meet, uid):
    peer = response_service.get_peer(meet, uid)
    peer_name = escape((peer.full_name or peer.username).split()[0]) if peer else "your neighbor"
    peer_bio = escape(peer.bio) if peer and peer.bio else None
    peer_avatar = escape(str(peer_name)[0].upper()) if peer else "?"
    return peer_name, peer_bio, peer_avatar


def _status_page(meet, uid, action):
    """Result page for a meet in a known state (used by GET and POST)."""
    peer_name, peer_bio, peer_avatar = _peer_display(meet, uid)

    if meet.status == "connected":
        extra = _peer_card(peer_avatar, peer_name, peer_bio) + \
            '<p style="font-size:14px;color:#5a6356;text-align:center">Hit <strong>Reply All</strong> on the intro email to say hello.</p>'
        return _respond_page(
            headline="You\'re both in! 🎉",
            message=f"You and {peer_name} both said yes. Check your inbox — we just sent you a mutual introduction with each other\'s contact details.",
            extra=extra,
        )
    if meet.status == "declined":
        return _respond_page(
            headline="This match is closed.",
            message="We\'ll pair you with someone new next Monday.",
            icon="—", icon_bg="#edf5f0", icon_color="#143c32",
        )
    if action == "accept":
        return _respond_page(
            headline="You said yes!",
            message=f"We\'ll let you know as soon as {peer_name} responds.",
        )
    return _respond_page(
        headline="No problem.",
        message="We\'ll pair you with someone new next Monday.",
        icon="—", icon_bg="#edf5f0", icon_color="#143c32",
    )


@app.route("/respond", methods=["GET"])
def respond_confirm():
    """READ-ONLY confirmation page.

    Email link scanners (Outlook SafeLinks etc.) prefetch GET links before
    the resident ever sees the email — so GET must never change state. The
    actual accept/decline happens via the POST forms rendered here.
    """
    meet_id, meet_id_int, uid, action, error = _parse_respond_request(request.args)
    if error:
        return error

    try:
        meet, my_action = response_service.get_response_state(meet_id_int, uid)
    except Exception as exc:
        logger.error("Failed to load respond state: %s", exc)
        return Response("Unable to load this match", status=400)

    # Meet already settled (or this resident already answered): show state.
    if meet.status in ("connected", "declined"):
        return _status_page(meet, uid, my_action or action)
    if my_action is not None:
        return _status_page(meet, uid, my_action)

    peer_name, peer_bio, peer_avatar = _peer_display(meet, uid)
    accept_sig = response_service.sign(meet_id, uid, "accept")
    decline_sig = response_service.sign(meet_id, uid, "decline")

    def _form(act, sig, label, style):
        return f"""
        <form method="post" action="/respond" style="display:inline-block;margin:6px">
          <input type="hidden" name="meet_id" value="{meet_id_int}">
          <input type="hidden" name="uid" value="{escape(uid)}">
          <input type="hidden" name="action" value="{act}">
          <input type="hidden" name="signature" value="{sig}">
          <button type="submit" style="{style}">{label}</button>
        </form>"""

    accept_btn = _form(
        "accept", accept_sig, "✓ Accept",
        "background:#143c32;color:#f5ede3;border:none;border-radius:100px;padding:0.9rem 2rem;font-size:15px;font-weight:600;cursor:pointer",
    )
    decline_btn = _form(
        "decline", decline_sig, "Decline",
        "background:#f0ebe3;color:#555;border:none;border-radius:100px;padding:0.9rem 2rem;font-size:15px;cursor:pointer",
    )
    extra = _peer_card(peer_avatar, peer_name, peer_bio) + \
        f'<div style="margin-top:1rem">{accept_btn}{decline_btn}</div>'

    return _respond_page(
        headline="Your neighbor match",
        message="One tap to confirm — meet this neighbor this week?",
        icon="☕", icon_bg="#edf5f0", icon_color="#143c32",
        extra=extra,
    )


@app.route("/respond", methods=["POST"])
def respond_act():
    """Records the accept/decline. State changes live ONLY here (never GET)."""
    meet_id, meet_id_int, uid, action, error = _parse_respond_request(request.form)
    if error:
        return error

    try:
        response_service.record_response(meet_id_int, uid, action)
    except Exception as exc:
        logger.error("Failed to store response: %s", exc)
        return Response("Unable to record response", status=400)

    meet = meet_repo.get_by_id(meet_id_int)
    return _status_page(meet, uid, action)


if __name__ == "__main__":
    log_dir = os.getenv("RCB_LOG_DIR", os.path.abspath(os.path.join(os.path.dirname(__file__), "../logs")))
    os.makedirs(log_dir, exist_ok=True)
    logger.add(
        os.path.join(log_dir, "match_{time}.log"),
        level="INFO",
        rotation=config["log"]["rotation"],
        compression="zip"
    )

    if not config["app"].get("adminToken"):
        logger.warning("adminToken is not configured; admin routes will be disabled")

    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
