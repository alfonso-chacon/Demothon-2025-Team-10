import glob
import json
import logging
import re
from datetime import datetime
import requests

# Constants
ASYNC_API_APPLICATION_TITLE_PATTERN = r'title: "([\w\.\s\-,;:\'\(\)]+)"'
ASYNC_API_APPLICATION_ID_PATTERN = r'x-ep-application-id: "([\w\.]+)"'
ASYNC_API_APPLICATION_VERSION_PATTERN = r'version: "([\w\.]+)"'
ASYNC_API_APPLICATION_VERSION_ID_PATTERN = r'x-ep-application-version-id: "([\w\.]+)"'
ASYNC_API_APPLICATION_VERSION_NAME_PATTERN = r'x-ep-displayname: "([\w\.\s]+)"'
ASYNC_API_APPLICATION_STATE_PATTERN = r'x-ep-state-name: "([\w\.]+)"'
ASYNC_API_APPLICATION_STATE_ID_PATTERN = r'x-ep-state-id: "([\w\.]+)"'

# logging
logger = logging.getLogger(__name__)

# Classes
class EventPortalApplication:
    lastChangeRecordId = None
    clientProfileName = None
    aclProfileName = None
    publishTopicExceptions = []
    clientUserName = None
    password = None
    clientAuthorizationGroupName = None
    def __init__(self, title, application_id, application_version, application_version_id, application_version_name, application_state, application_state_id):
        self.applicationTitle = title
        self.applicationId = application_id
        self.applicationVersion = application_version
        self.applicationVersionId = application_version_id
        self.applicationVersionName = application_version_name
        self.applicationState = application_state
        self.applicationStateId = application_state_id

    def __str__(self):
        return json.dumps(self.__dict__)

# Methods
def to_pretty_json(ugly_json):
    parsed = json.loads(ugly_json)
    pretty_json = json.dumps(parsed, indent=4)
    return pretty_json

def get_match(pattern, line):
    match_group = None
    match = re.match(pattern, line)
    if match:
        match_group = match.group(1)
        print(f"Match: '{match_group}'")

    return match, match_group


def get_application_domain(token, application_domain_name):
    url = f"https://api.solace.cloud/api/v2/architecture/applicationDomains?pageSize=100&pageNumber=1&name={application_domain_name}"

    headers = {
        "accept": "application/json",
        "authorization": f"Bearer {token}"
    }

    response = requests.get(url, headers=headers)

    if response.status_code != 200:
        raise Exception(f"Getting application domain with name: {application_domain_name} failed! - {str(response.json())}")
    return response.text

def get_application_domain_id_by_name(token, application_domain_names):
    application_domain_ids = []
    for application_domain_name in application_domain_names:
        response = get_application_domain(token, application_domain_name)
        json_response = json.loads(response)
        data = json_response.get('data')

        if data is not None:
            for record in data:
                application_domain_id = record.get('id')
                print(f"Application domain Id retrieved: {application_domain_id}")
                application_domain_ids.append(application_domain_id)
    return application_domain_ids

def get_application_list_by_app_domain_id(token, application_domain_id):
    url = f"https://api.solace.cloud/api/v2/architecture/applications?pageSize=100&pageNumber=1&applicationDomainId={application_domain_id}"

    headers = {
        "accept": "application/json;charset=UTF-8",
        "authorization": f"Bearer {token}"
    }
    response = requests.get(url, headers=headers)
    if response.status_code != 200:
        raise Exception(f"Getting list of applications for application domain with id: {application_domain_id} failed! - {str(response.json())}")

    json_response = json.loads(response.text)
    data = json_response.get('data')

    application_list = []

    if data is not None:
        for record in data:
            application_id = record.get('id')
            application_title = record.get('name')

            ep_application = EventPortalApplication(application_title, application_id, application_version=None,
                                                    application_version_id=None, application_version_name=None, application_state=None,
                                                    application_state_id=None)
            print(ep_application)
            application_list.append(ep_application)

    return application_list

def get_latest_application_version(token, application):
    url = f"https://api.solace.cloud/api/v2/architecture/applicationVersions?pageSize=100&pageNumber=1&applicationIds={application.applicationId}"

    headers = {
        "accept": "application/json;charset=UTF-8",
        "authorization": f"Bearer {token}"
    }

    response = requests.get(url, headers=headers)
    print(response.text)
    if response.status_code != 200:
        raise Exception(f"Getting last version for application name: {application.applicationTitle}, id: {application.applicationId} failed! - {str(response.json())}")

    json_response = json.loads(response.text)
    data = json_response.get('data')

    last_version_id = None
    last_version = None
    last_datetime = None

    if data is not None:
        for record in data:
            created_time = record.get('createdTime')
            version_id = record.get('id')
            version_name = record.get('version')
            datetime_object = datetime.fromisoformat(created_time)
            print(datetime_object)

            if last_datetime is None:
                last_datetime = datetime_object
                last_version_id = version_id
                last_version = version_name
            elif datetime_object > last_datetime:
                last_datetime = datetime_object
                last_version_id = version_id
                last_version = version_name

    application.applicationVersion = last_version
    application.applicationVersionId = last_version_id

    print(application)
    return None

def get_applications_from_yaml_files():
    application_list = []
    files = glob.glob('./**/*.yaml', recursive=True)

    for file in files:
        print(file)
        with open(file, 'r') as o_file:
            application_title = None
            application_id = None
            application_version = None
            application_version_id = None
            application_version_name = None
            application_state = None
            application_state_id = None

            for line in o_file:
                # Removes trailing newline characters
                line = line.strip()
                print(line)

                match, match_group = get_match(ASYNC_API_APPLICATION_TITLE_PATTERN, line)
                if match:
                    application_title = match_group

                match, match_group = get_match(ASYNC_API_APPLICATION_ID_PATTERN, line)
                if match:
                    application_id = match_group

                match, match_group = get_match(ASYNC_API_APPLICATION_VERSION_PATTERN, line)
                if match:
                    application_version = match_group

                match, match_group = get_match(ASYNC_API_APPLICATION_VERSION_ID_PATTERN, line)
                if match:
                    application_version_id = match_group

                match, match_group = get_match(ASYNC_API_APPLICATION_VERSION_NAME_PATTERN, line)
                if match:
                    application_version_name = match_group

                match, match_group = get_match(ASYNC_API_APPLICATION_STATE_PATTERN, line)
                if match:
                    application_state = match_group

                match, match_group = get_match(ASYNC_API_APPLICATION_STATE_ID_PATTERN, line)
                if match:
                    application_state_id = match_group


            ep_application = EventPortalApplication(application_title, application_id, application_version,
                                                    application_version_id, application_version_name, application_state, application_state_id)
            print(ep_application)
            application_list.append(ep_application)

    return application_list

def get_modeled_event_meshes(token):
    url = "https://api.solace.cloud/api/v2/architecture/about/eventMeshes?pageSize=100&pageNumber=1&sort=name%3Aasc"

    headers = {
        "accept": "*/*",
        "authorization": f"Bearer {token}"
    }
    response = requests.get(url, headers=headers, verify=False)
    if response.status_code != 200:
        raise Exception("Getting modeled event meshes failed: " + str(response.json()))
    return response.text

def get_messaging_services(token):
    url = "https://api.solace.cloud/api/v2/architecture/messagingServices?pageSize=100&pageNumber=1&sort=name%3Aasc"

    headers = {
        "accept": "application/json",
        "authorization": f"Bearer {token}"    }

    response = requests.get(url, headers=headers)
    if response.status_code != 200:
        raise Exception("Getting list of messaging services failed: " + str(response.json()))
    return response.text

def get_application_list_by_name(token, application_name, application):
    url = f"https://api.solace.cloud/api/v2/architecture/applications?pageSize=100&pageNumber=1&name={application_name}"

    headers = {
        "accept": "application/json;charset=UTF-8",
        "authorization": f"Bearer {token}"
    }

    logger.info(
        f"Getting application list by name: {application_name}")
    response = requests.get(url, headers=headers)

    if response.status_code != 200:
        raise Exception(f"Getting Application List by name: {application_name} failed! - error details: " + str(response.json()))

    json_response = json.loads(response.text)
    data = json_response.get('data')
    if data is not None:
        for record in data:
            application.applicationTitle = record.get('name')
            application.applicationId = record.get('id')

    print(f"Application retrieved: {application}")
    return None

def get_application_version_by_name(token, version_name, application):
    url = f"https://api.solace.cloud/api/v2/architecture/applicationVersions?pageSize=100&pageNumber=1&applicationIds={application.applicationId}"

    headers = {
        "accept": "application/json;charset=UTF-8",
        "authorization": f"Bearer {token}"
    }

    logger.info(f"Getting application versions for Application: {application.applicationTitle}")
    response = requests.get(url, headers=headers)

    if response.status_code != 200:
        raise Exception(f"Getting application versions for application: {application.applicationTitle} failed! - error details: " + str(response.json()))

    json_response = json.loads(response.text)
    data = json_response.get('data')
    if data is not None:
        for record in data:
            version = record.get('version')
            if version == version_name:
                application.applicationVersion = version
                application.applicationVersionId = record.get('id')
                application.applicationVersionName = record.get('displayName')
                application.applicationStateId = record.get('stateId')
                if application.applicationStateId == '1':
                    application.applicationState = 'DRAFT'
                elif application.applicationStateId == '2':
                    application.applicationState = 'RELEASED'
                else:
                    application.applicationState = 'X'

    print(f"Application retrieved: {application}")
    return None

def get_broker_id_by_name(token, broker_name):
    response = get_messaging_services(token)

    broker_id = None

    json_response = json.loads(response)
    data = json_response.get('data')
    if data is not None:
        for record in data:
            t_broker_name = record.get('name')
            if t_broker_name == broker_name:
                broker_id = record.get('id')

    print(f"BrokerId retrieved: {broker_id}")
    return broker_id

def get_broker_service_id_by_name(token, broker_name):
    url = f"https://api.solace.cloud/api/v2/missionControl/eventBrokerServices?customAttributes=name%3D%3D{broker_name}&pageNumber=1&pageSize=100"

    headers = {
        "accept": "application/json",
        "authorization": f"Bearer {token}"
    }

    logger.info(f"Getting Broker Service Id by Name: {broker_name}")
    response = requests.get(url, headers=headers)

    if response.status_code != 200:
        raise Exception(f"Getting Broker Service Id by Name: {broker_name} failed! - error details: " + str(response.json()))

    broker_service_id = None

    json_response = json.loads(response.text)
    data = json_response.get('data')
    if data is not None:
        for record in data:
            broker_service_id = record.get('id')

    print(f"BrokerServiceId retrieved: {broker_service_id}")
    return broker_service_id

def get_application_version(token, application):
    url = f"https://api.solace.cloud/api/v2/architecture/applicationVersions?pageSize=100&pageNumber=1&applicationIds={application.applicationId}&ids={application.applicationVersionId}"

    headers = {
        "accept": "application/json;charset=UTF-8",
        "authorization": f"Bearer {token}"
    }
    logger.info(
        f"Validating Application: {application.applicationTitle}, version: {application.applicationVersion} - {application.applicationVersionName}, state: {application.applicationState}")
    response = requests.get(url, headers=headers)

    if response.status_code != 200:
        raise Exception(f"Validation for Application: {application.applicationTitle}, version: {application.applicationVersion} - {application.applicationVersionName}, state: {application.applicationState} failed! - error details: " + str(response.json()))

    return response.text

def get_application_async_api_specification(token, application, format):
    url = f"https://api.solace.cloud/api/v2/architecture/applicationVersions/{application.applicationVersionId}/asyncApi?format={format}&showVersioning=true&includedExtensions=all&asyncApiVersion=2.5.0"

    headers = {
        "accept": "application/json",
        "authorization": f"Bearer {token}"
    }

    logger.info(
        f"Getting AsyncAPI specification for Application: {application.applicationTitle}, version: {application.applicationVersion} - {application.applicationVersionName}, state: {application.applicationState}")
    response = requests.get(url, headers=headers)
    if response.status_code != 200:
        raise Exception(f"Getting AsyncAPI specification for Application: {application.applicationTitle}, version: {application.applicationVersion} - {application.applicationVersionName}, state: {application.applicationState} failed! - error details: " + str(response.json()))

    print(response.text)
    return response.text

def get_application_client_profile(token, application):
    url = f"https://api.solace.cloud/api/v2/architecture/designer/configuration/solaceClientProfileNames?pageSize=20&pageNumber=1&entityIds={application.applicationVersionId}"

    headers = {
        "accept": "application/json;charset=UTF-8",
        "authorization": f"Bearer {token}"
    }

    logger.info(f"Getting client profile for Application: {application.applicationTitle}, version: {application.applicationVersion} - {application.applicationVersionName}, state: {application.applicationState}")
    response = requests.get(url, headers=headers)

    if response.status_code != 200:
        raise Exception(f"Getting client profile for Application: {application.applicationTitle}, version: {application.applicationVersion} - {application.applicationVersionName}, state: {application.applicationState} failed! - error details: " + str(response.json()))

    return response.text

def create_application_client_profile(token, broker_service_id, client_profile_name):
    url = f"https://api.solace.cloud/api/v2/missionControl/eventBrokerServices/{broker_service_id}/clientProfiles"

    payload = {
        "name": f"{client_profile_name}",
    }
    headers = {
        "accept": "application/json",
        "content-type": "application/json",
        "authorization": f"Bearer {token}"
    }

    logger.info(f"Creating client profile with name: {client_profile_name}")
    response = requests.post(url, json=payload, headers=headers)

    if response.status_code != 200 and response.status_code != 202 and response.status_code != 400:
        raise Exception(f"Creation of client profile with name: {client_profile_name} failed! - error details: " + str(response.json()))

    print(response.text)


def get_application_client_username(token, broker_id, application):
    url = f"https://api.solace.cloud/api/v2/architecture/designer/configuration/solaceClientUsernames?pageSize=20&pageNumber=1&eventBrokerIds={broker_id}&entityIds={application.applicationId}"

    headers = {
        "accept": "application/json;charset=UTF-8",
        "authorization": f"Bearer {token}"
    }
    logger.info(url)
    logger.info(
        f"Getting client username for Application: {application.applicationTitle}, version: {application.applicationVersion} - {application.applicationVersionName}, state: {application.applicationState} - BrokerId: {broker_id}")
    response = requests.get(url, headers=headers)

    if response.status_code != 200:
        raise Exception(f"Getting client username for Application: {application.applicationTitle}, version: {application.applicationVersion} - {application.applicationVersionName}, state: {application.applicationState} failed! - error details: " + str(response.json()))

    return response.text


def get_application_authorization_group(token, broker_id, application):
    url = f"https://api.solace.cloud/api/v2/architecture/designer/configuration/solaceAuthorizationGroups?pageSize=100&pageNumber=1&eventBrokerIds={broker_id}&entityIds={application.applicationId}"

    headers = {
        "accept": "application/json;charset=UTF-8",
        "authorization": f"Bearer {token}"
    }
    logger.info(url)
    logger.info(
        f"Getting client authorization group for Application: {application.applicationTitle}, version: {application.applicationVersion} - {application.applicationVersionName}, state: {application.applicationState} - BrokerId: {broker_id}")
    response = requests.get(url, headers=headers)

    if response.status_code != 200:
        raise Exception(f"Getting client client Authorization group for Application: {application.applicationTitle}, version: {application.applicationVersion} - {application.applicationVersionName}, state: {application.applicationState} failed! - error details: " + str(response.json()))

    return response.text

def create_application_client_username(token, broker_id, application):
    url = "https://api.solace.cloud/api/v2/architecture/designer/configuration/solaceClientUsernames"

    payload = {
        #"action": "deploy",
        #"applicationVersionId": f"{application.applicationVersionId}",
        #"eventBrokerId": f"{broker_id}",

        "value": {
            "clientUsername": f"{application.clientUserName}",
            "password": f"{application.password}"
        },
        "configurationTypeId": "solaceClientUsername",
        "contextType": "EVENT_BROKER",
        "contextId": f"{broker_id}",
        "entityId": f"{application.applicationId}"
    }

    headers = {
        "accept": "application/json;charset=UTF-8",
        "content-type": "application/json;charset=UTF-8",
        "authorization": f"Bearer {token}"
    }

    response = requests.post(url, json=payload, headers=headers)
    if response.status_code != 200 and response.status_code != 201:
        raise Exception(f"Creating client Username for Application: {application.applicationTitle}, version: {application.applicationVersion} - {application.applicationVersionName}, state: {application.applicationState} failed! - error details: " + str(response.json()))

    return response.text

def create_application_authorization_group(token, broker_id, application):
    url = "https://api.solace.cloud/api/v2/architecture/designer/configuration/solaceAuthorizationGroups"

    payload = {
        "action": "deploy",
        "applicationVersionId": f"{application.applicationVersionId}",
        "eventBrokerId": f"{broker_id}",

        "value": {
            "clientUsername": f"{application.clientUserName}",
            "authorizationGroupName": f"{application.clientAuthorizationGroupName}"
        },
        "configurationTypeId": "solaceAuthorizationGroup",
        "contextType": "EVENT_BROKER",
        "contextId": f"{broker_id}",
        "entityId": f"{application.applicationId}"
    }

    headers = {
        "accept": "application/json;charset=UTF-8",
        "content-type": "application/json;charset=UTF-8",
        "authorization": f"Bearer {token}"
    }

    response = requests.post(url, json=payload, headers=headers)
    if response.status_code != 200 and response.status_code != 201:
        raise Exception(f"Creating client client Authorization group for Application: {application.applicationTitle}, version: {application.applicationVersion} - {application.applicationVersionName}, state: {application.applicationState} failed! - error details: " + str(response.json()))

    return response.text

def deploy_application_to_runtime(token, broker_id, action, application):
    url = "https://api.solace.cloud/api/v2/architecture/runtimeManagement/applicationDeployments"

    payload = {
        "action": f"{action}",
        "applicationVersionId": f"{application.applicationVersionId}",
        "eventBrokerId": f"{broker_id}"
    }
    headers = {
        "accept": "*/*",
        "content-type": "application/json",
        "authorization": f"Bearer {token}"
    }
    logger.info(f"Pushing application: {application.applicationTitle}, version: {application.applicationVersion} - {application.applicationVersionName}, state: {application.applicationState} to Runtime Broker with Id: {broker_id}")
    response = requests.post(url, json=payload, headers=headers, verify=False)
    if response.status_code != 200:
        raise Exception(f"Pushing application: {application.applicationTitle} to Runtime Broker with Id: {broker_id} failed! - error details: " + str(response.json()))

    json_response = json.loads(response.text)

    data = json_response.get('data')
    if data is not None:
        application.lastChangeRecordId = data.get('changeRecordId')

    print(f"changeRecordId: {application.lastChangeRecordId}")
    return response.text

def get_application_deployment_status(token, broker_id, application):
    url = f"https://api.solace.cloud/api/v2/architecture/runtimeManagement/applications/{application.applicationId}/configurationPushJobs?pageSize=20&pageNumber=1&changeRecordIds={application.lastChangeRecordId}"

    headers = {
        "accept": "*/*",
        "authorization": f"Bearer {token}"
    }
    logger.info(
        f"Getting deployment status for application: {application.applicationTitle}, version: {application.applicationVersion} - {application.applicationVersionName}, state: {application.applicationState} to Runtime Broker with Id: {broker_id}")
    response = requests.get(url, headers=headers)
    if response.status_code != 200:
        raise Exception(f"Getting deployment status for Application: {application.applicationTitle} ChangeRecordId: {application.lastChangeRecordId} failed! - error details: " + str(response.json()))

    return response.text