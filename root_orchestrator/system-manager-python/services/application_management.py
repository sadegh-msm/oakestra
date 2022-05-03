from ext_requests.apps_db import *


def register_app(application, userid):
    application['userId'] = userid
    application['microservices'] = []
    return mongo_add_application(application)


def add_service_to_app(app_id, service_id, userid):
    application = get_user_app(userid, app_id)
    application['microservices'].append(service_id)
    mongo_update_application_microservices(app_id, application['microservices'])


def remove_service_from_app(app_id, service_id, userid):
    application = get_user_app(userid, app_id)
    application['microservices'].remove(service_id)
    mongo_update_application_microservices(app_id, application['microservices'])


def update_app(appid, userid, fields):
    # TODO: fields validation
    return mongo_update_application(appid, userid, fields)


def delete_app(appid, userid):
    return mongo_delete_application(appid, userid)


def users_apps(userid):
    return mongo_get_applications_of_user(userid)


def all_apps():
    return mongo_get_all_applications()


def get_user_app(userid, appid):
    return mongo_find_app_by_id(appid, userid)
