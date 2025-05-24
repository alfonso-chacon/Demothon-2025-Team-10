import argparse
import json
import logging
import os
import random
import shutil
import string
import sys
import time
import http.client as http_client

import requests
import urllib3

import solace_ep_integration as sepi

# Constants
WAIT_TIME_IN_SECONDS = 1
ACTION_DEPLOY = 'deploy'
ACTION_UNDEPLOY = 'undeploy'

# logging
logger = logging.getLogger(__name__)

'''
Validate that the application with that version id exists in EP designer
'''
def validate_application_version(token, application):
    txt_response = sepi.get_application_version(token, application)
    pretty_json = sepi.to_pretty_json(txt_response)
    print(pretty_json)

    json_response = json.loads(txt_response)
    data = json_response.get('data')
    if data is not None:
        if len(data) == 0:
            raise Exception(
                f"Application: {application.applicationTitle}, version: {application.applicationVersion} - {application.applicationVersionName}, state: {application.applicationState} does not Exists on Event Portal Designer!. Aborting!")

    return None

def write_application_async_api_specification(token, application):
    txt_response = sepi.get_application_async_api_specification(token, application, 'yaml')
    #pretty_json = sepi.to_pretty_json(txt_response)
    print(txt_response)


    async_api_file = f"out/yaml/{application.applicationTitle}_v{application.applicationVersion}.yaml".lower()
    async_api_file = async_api_file.replace(" ", "_")
    os.makedirs(os.path.dirname(async_api_file), exist_ok=True)

    logger.info(
        f"Writing AsyncAPI specification for Application: {application.applicationTitle}, version: {application.applicationVersion} - {application.applicationVersionName}, state: {application.applicationState} to file: {async_api_file}")
    with open(async_api_file, "w") as file:
        file.write(txt_response)

    return None

def validate_application_client_profile(token, broker_service_id, application):
    txt_response = sepi.get_application_client_profile(token, application)
    pretty_json = sepi.to_pretty_json(txt_response)
    print(pretty_json)

    client_profile_name = None
    json_response = json.loads(txt_response)
    data = json_response.get('data')
    if data is not None:
        if len(data) == 0:
            raise Exception(
                f"Application: {application.applicationTitle}, version: {application.applicationVersion} - {application.applicationVersionName}, state: {application.applicationState} does not have a Client Profile! Create one in Event Portal Designer before continue. Aborting!")
        else:
            record = data[0]
            if record is not None:
                client_profile_name = record.get('identifier')

    sepi.create_application_client_profile(token, broker_service_id, client_profile_name)
    return None

def validate_application_client_username(token, broker_id, application):
    txt_response = sepi.get_application_client_username(token, broker_id, application)
    pretty_json = sepi.to_pretty_json(txt_response)
    print(pretty_json)

    json_response = json.loads(txt_response)
    data = json_response.get('data')
    if data is not None:
        if len(data) == 0:
            logger.warning(
                f"Application: {application.applicationTitle}, version: {application.applicationVersion} - {application.applicationVersionName}, state: {application.applicationState} does not have an Authorization Group (OAuth or LDAP)!.")

            logger.warning("Deploying the App for the Client Username...")
            deploy_undeploy_application_to_runtime(token, broker_id, ACTION_DEPLOY, application)
            get_deployment_status_single_application_to_runtime(token, broker_id, application)

            logger.warning("Creating the Client Username..")
            txt_response = sepi.create_application_client_username(token, broker_id, application)
            pretty_json = sepi.to_pretty_json(txt_response)
            print(pretty_json)

    return None


def deploy_undeploy_application_to_runtime(token, broker_id, action, app):
    json_response = sepi.deploy_application_to_runtime(token, broker_id, action, app)
    pretty_json = sepi.to_pretty_json(json_response)
    print(pretty_json)

def get_deployment_status_single_application_to_runtime(token, broker_id, app):
    status = 'in_progress'

    while status == 'in_progress':
        txt_response = sepi.get_application_deployment_status(token, broker_id, app)
        pretty_json = sepi.to_pretty_json(txt_response)
        print(pretty_json)

        json_response = json.loads(txt_response)
        data = json_response.get('data')
        if data is not None:
            if len(data) == 0:
                raise Exception(
                    f"Cannot find Deployment for Application: {app.applicationTitle}, version: {app.applicationVersion} - {app.applicationVersionName}, state: {app.applicationState}!. Aborting!")
            record = data[0]
            if record is not None:
                status = record.get('status')

        if status == 'in_progress':
            logger.info(f"Waiting 500 milliseconds before querying for deployment status...")
            time.sleep(500 / 1000)

        if status == 'error':
            raise Exception(
                f"Deployment for application: {app.applicationTitle}, version: {app.applicationVersion} - {app.applicationVersionName}, state: {app.applicationState} to Runtime Broker with Id: {broker_id} failed!")

    return None

def deploy_applications_to_runtime(token, broker_service_id, broker_id, application_list):
    # Validate that the application with that version id exists in EP designer
    for app in application_list:
        validate_application_version(token, app)

    for app in application_list:
        validate_application_client_profile(token, broker_service_id, app)

    for app in application_list:
        validate_application_client_username(token, broker_id, app)

    for app in application_list:
        deploy_undeploy_application_to_runtime(token, broker_id, ACTION_DEPLOY, app)

    logger.info(f"Waiting {WAIT_TIME_IN_SECONDS} second(s) before querying for deployment status...")
    time.sleep(WAIT_TIME_IN_SECONDS)

    for app in application_list:
        get_deployment_status_single_application_to_runtime(token, broker_id, app)

    return None

def undeploy_applications_to_runtime(token, broker_id, application_list):
    # Validate that the application with that version id exists in EP designer
    for app in application_list:
        validate_application_version(token, app)

    for app in application_list:
        deploy_undeploy_application_to_runtime(token, broker_id, ACTION_UNDEPLOY, app)

    logger.info(f"Waiting {WAIT_TIME_IN_SECONDS} second(s) before querying for undeployment status...")
    time.sleep(WAIT_TIME_IN_SECONDS)

    for app in application_list:
        get_deployment_status_single_application_to_runtime(token, broker_id, app)

    return None


def get_client_username_acl(semp_config_url, semp_username , semp_password, msg_vpn_name, client_username, application):
    url = f"{semp_config_url}/msgVpns/{msg_vpn_name}/clientUsernames/{client_username}"

    response = requests.get(url, auth=(semp_username, semp_password))

    if response.status_code != 200:
        raise Exception("Getting client username ACL failed: " + str(response.json()))

    json_response = response.json()["data"]

    application.aclProfileName = json_response.get('aclProfileName')
    return None

def get_client_username_acl_publish_topic_exceptions(semp_config_url, semp_username , semp_password, msg_vpn_name, application):
    url = f"{semp_config_url}/msgVpns/{msg_vpn_name}/aclProfiles/{application.aclProfileName}/publishTopicExceptions"

    response = requests.get(url, auth=(semp_username, semp_password))

    if response.status_code != 200:
        raise Exception("Getting client username ACL publish topic exceptions failed: " + str(response.json()))

    json_response_list = response.json()["data"]

    application.publishTopicExceptions = []

    for topic_exception in json_response_list:
        application.publishTopicExceptions.append(topic_exception.get('publishTopicException'))

    return None

def get_client_username_queues(semp_config_url, semp_username , semp_password, msg_vpn_name, apps_dict):
    url = f"{semp_config_url}/msgVpns/{msg_vpn_name}/queues"

    response = requests.get(url, auth=(semp_username, semp_password))

    if response.status_code != 200:
        raise Exception("Getting client username queues failed: " + str(response.json()))

    json_response_list = response.json()["data"]

    for queue in json_response_list:
        queue_name = queue.get('queueName')
        owner = queue.get('owner')

        #print(f"q: {queue_name}, o:{owner}")

        if owner in apps_dict:
            app = apps_dict[owner]
            if app.queues is None or len(app.queues) == 0:
                app.queues = []
            #print(f" Adding q: {queue_name}, o:{owner} to: {app}")
            app.queues.append(queue_name)
            #print(f" App: {app}")

    return None

def generate_random_string(n):
    characters = string.ascii_letters + string.digits  # Includes uppercase, lowercase, and digits
    random_string = ''.join(random.choice(characters) for _ in range(n))
    return random_string

def write_sdk_publishers(host, msg_vpn, application):

    if len(application.publishTopicExceptions) == 0:
        return None

    topics_to_publish = ','.join(application.publishTopicExceptions)
    topics_to_publish = topics_to_publish.replace("*", generate_random_string(5))

    # 4 messages per second for 10 minutes
    file_content = f'set SOLACE_VM_ARGS=-javaagent:C:/Solace/GitHub/Demothon-2025-Team-10/out/publisher/sdkperf/lib/opentelemetry-javaagent.jar -Dotel.javaagent.extensions=C:/Solace/GitHub/Demothon-2025-Team-10/out/publisher/sdkperf/lib/solace-opentelemetry-jms-integration-1.1.0.jar -Dotel.traces.exporter=otlp -Dotel.metrics.exporter=none -Dotel.instrumentation.jms.enabled=true -Dotel.javaagent.debug=false -Dotel.propagators=solace_jms_tracecontext -Dotel.resource.attributes=service.name={application.clientUserName} -Dotel.exporter.otlp.endpoint=http://ajcr-docker.eastus.cloudapp.azure.com:14317 -Dotel.exporter.otlp.headers="Info=demothon-2025" -Dotel.bsp.schedule.delay=500 -Dotel.bsp.max.queue.size=1000 -Dotel.bsp.max.export.batch.size=5 -Dotel.bsp.export.timeout=10000' + '\n'
    file_content = file_content + f'cd sdkperf' + '\n'
    file_content = file_content + f"sdkperf_jms.bat -cip={host} -cu={application.clientUserName}@{msg_vpn} -cp={application.password} -ptl={topics_to_publish} -mn=2400 -mt=persistent -mr=4 -msx=1024" + '\n'

    publish_file = f"out/publisher/pub_{application.applicationTitle}_v{application.applicationVersion}.bat".lower()
    publish_file = publish_file.replace(" ", "_")
    publish_file = publish_file.replace("(", "_")
    publish_file = publish_file.replace(")", "_")
    os.makedirs(os.path.dirname(publish_file), exist_ok=True)

    logger.info(
        f"Writing Publisher bat file for Application: {application.applicationTitle}, version: {application.applicationVersion} - {application.applicationVersionName}, state: {application.applicationState} to file: {publish_file}")
    with open(publish_file, "w") as file:
        file.write(file_content)

    return None

def write_sdk_subscribers(host, msg_vpn, application):

    if len(application.queues) == 0:
        return None

    queues_to_subscribe = ','.join(application.queues)
    # topics_to_publish = topics_to_publish.replace("*", generate_random_string(5))

    # 4 messages per second for 10 minutes
    file_content = f'set SOLACE_VM_ARGS=-javaagent:C:/Solace/GitHub/Demothon-2025-Team-10/out/publisher/sdkperf/lib/opentelemetry-javaagent.jar -Dotel.javaagent.extensions=C:/Solace/GitHub/Demothon-2025-Team-10/out/publisher/sdkperf/lib/solace-opentelemetry-jms-integration-1.1.0.jar -Dotel.traces.exporter=otlp -Dotel.metrics.exporter=none -Dotel.instrumentation.jms.enabled=true -Dotel.javaagent.debug=false -Dotel.propagators=solace_jms_tracecontext -Dotel.resource.attributes=service.name={application.clientUserName} -Dotel.exporter.otlp.endpoint=http://ajcr-docker.eastus.cloudapp.azure.com:14317 -Dotel.exporter.otlp.headers="Info=demothon-2025" -Dotel.bsp.schedule.delay=500 -Dotel.bsp.max.queue.size=1000 -Dotel.bsp.max.export.batch.size=5 -Dotel.bsp.export.timeout=10000' + '\n'
    file_content = file_content + f'cd sdkperf' + '\n'
    file_content = file_content + f"sdkperf_jms.bat -cip={host} -cu={application.clientUserName}@{msg_vpn} -cp={application.password} -sql={queues_to_subscribe}"

    subscriber_file = f"out/subscriber/sub_{application.applicationTitle}_v{application.applicationVersion}.bat".lower()
    subscriber_file = subscriber_file.replace(" ", "_")
    subscriber_file = subscriber_file.replace("(", "_")
    subscriber_file = subscriber_file.replace(")", "_")
    os.makedirs(os.path.dirname(subscriber_file), exist_ok=True)

    logger.info(
        f"Writing Subscriber bat file for Application: {application.applicationTitle}, version: {application.applicationVersion} - {application.applicationVersionName}, state: {application.applicationState} to file: {subscriber_file}")
    with open(subscriber_file, "w") as file:
        file.write(file_content)

    return None

def write_sdk_publish_run_all():

    file_content = 'for /r "." %%a in (*.bat) do start "" "%%~fa"'

    publish_file = f"out/publisher/pub_run_all.cmd"
    publish_file = publish_file.replace(" ", "_")
    os.makedirs(os.path.dirname(publish_file), exist_ok=True)

    logger.info(
        f"Writing Publisher run All cmd file")
    with open(publish_file, "w") as file:
        file.write(file_content)

    return None

def write_sdk_subscribe_run_all():

    file_content = 'for /r "." %%a in (*.bat) do start "" "%%~fa"'

    publish_file = f"out/subscriber/sub_run_all.cmd"
    publish_file = publish_file.replace(" ", "_")
    os.makedirs(os.path.dirname(publish_file), exist_ok=True)

    logger.info(
        f"Writing Subscriber run All cmd file")
    with open(publish_file, "w") as file:
        file.write(file_content)

    return None
# Main
def main(argv):

    # Parse parameters
    parser = argparse.ArgumentParser(description="Push Applications to Broker Runtime")
    parser.add_argument("-token", type=str, required=True, help="Event Portal Auth Token")

    parser.add_argument("-applicationDomainList", type=str, required=True, help="Comma separated list of Application Domain Name")

    parser.add_argument("-brokerName", type=str, required=True, help="Runtime broker Name")
    parser.add_argument("-msgVpnName", type=str, required=True, help="Message VPN")
    parser.add_argument("-sempConfigUrl", type=str, required=True, help="SEMP Config URL")
    parser.add_argument("-sempUsername", type=str, required=True, help="SEMP username")
    parser.add_argument("-sempPassword", type=str, required=True, help="SEMP password")
    parser.add_argument("-msgUrl", type=str, required=True, help="Broker SMF URL")



    parser.add_argument("-action", type=str, required=True, help="deploy/undeploy")


    args = parser.parse_args()

    print(f"Arguments: Token: ***, brokerName: {args.brokerName}, action: {args.action} " +
          f"applicationDomainList: {args.applicationDomainList}")
    # , applicationVersion: {args.applicationVersion}, clientUsername: {args.clientUsername}, clientAuthorizationGroupName: {args.clientAuthorizationGroupName}")

    # Get Application Domain Ids
    application_domain_names = args.applicationDomainList.split(",")

    application_domain_ids = sepi.get_application_domain_id_by_name(args.token, application_domain_names)
    if application_domain_ids is None or len(application_domain_ids) == 0:
        raise Exception(f"Could not find an application domains ids for: {args.applicationDomainList}")

    application_list = []
    for application_domain_id in application_domain_ids:
        application_list_app_domain = sepi.get_application_list_by_app_domain_id(args.token, application_domain_id)
        application_list.extend(application_list_app_domain)

    if application_list is None or len(application_list) == 0:
        raise Exception(f"Could not get applications for application domains: {args.applicationDomainList}")

    for app in application_list:
        sepi.get_latest_application_version(args.token, app)
        #print(app)

    # Get Broker ID
    broker_id = sepi.get_broker_id_by_name(args.token, args.brokerName)
    if broker_id is None:
        raise Exception(f"Could not find an broker with name: {args.brokerName}")

    # Get Broker Service ID
    broker_service_id = sepi.get_broker_service_id_by_name(args.token, args.brokerName)
    if broker_service_id is None:
        raise Exception(f"Could not find an broker service with name: {args.brokerName}")

    # Iterate through all files in the directory
    os.makedirs(os.path.dirname("out/yaml/1.txt"), exist_ok=True)
    for filename in os.listdir("out/yaml"):
        file_path = os.path.join("out/yaml", filename)
        # Check if it's a file before deleting
        if os.path.isfile(file_path):
            os.remove(file_path)
            print(f"Deleted: {file_path}")

    os.makedirs(os.path.dirname("out/publisher/1.txt"), exist_ok=True)
    for filename in os.listdir("out/publisher"):
        file_path = os.path.join("out/publisher", filename)
        # Check if it's a file before deleting
        if os.path.isfile(file_path):
            os.remove(file_path)
            print(f"Deleted: {file_path}")

    os.makedirs(os.path.dirname("out/subscriber/1.txt"), exist_ok=True)
    for filename in os.listdir("out/subscriber"):
        file_path = os.path.join("out/subscriber", filename)
        # Check if it's a file before deleting
        if os.path.isfile(file_path):
            os.remove(file_path)
            print(f"Deleted: {file_path}")

    shutil.copytree("libraries/sdkperf", "out/publisher/sdkperf", dirs_exist_ok=True)
    shutil.copytree("libraries/sdkperf", "out/subscriber/sdkperf", dirs_exist_ok=True)
    shutil.copytree("libraries/otel", "out/publisher/lib", dirs_exist_ok=True)
    shutil.copytree("libraries/otel", "out/subscriber/lib", dirs_exist_ok=True)

    # print all the apps to console
    for app in application_list:
        print(app)
        # Write Async API spec to json file
        write_application_async_api_specification(args.token, app)

    # Scan current workspace to get all the yaml files and read them
    application_list = sepi.get_applications_from_yaml_files()

    # print all the apps to console
    for app in application_list:
        print(app)

    # Set username and password
    for app in application_list:
        client_user_name = app.applicationTitle.lower()
        client_user_name = client_user_name.replace(" ", "_")
        client_user_name = client_user_name.replace("(", "")
        client_user_name = client_user_name.replace(")", "")
        client_user_name = client_user_name.replace("_", "")
        app.clientUserName = client_user_name
        app.password = "password"

    # print all the apps to console
    for app in application_list:
        print(app)

    if args.action == ACTION_UNDEPLOY:
        undeploy_applications_to_runtime(args.token, broker_id, application_list)
        return None


    if args.action == ACTION_DEPLOY:
        # deploy applications to runtime broker
        deploy_applications_to_runtime(args.token, broker_service_id, broker_id, application_list)

    apps_dict = {}
    # Get ACLs from broker
    for app in application_list:
        get_client_username_acl(args.sempConfigUrl, args.sempUsername, args.sempPassword, args.msgVpnName, app.clientUserName, app)
        get_client_username_acl_publish_topic_exceptions(args.sempConfigUrl, args.sempUsername, args.sempPassword, args.msgVpnName, app)
        print(app)
        apps_dict[app.clientUserName] = app

    # Get Queues in Msg VPN
    get_client_username_queues(args.sempConfigUrl, args.sempUsername, args.sempPassword, args.msgVpnName, apps_dict)

    # Write publisher Apps
    for app in application_list:
        print(app)
        write_sdk_publishers(args.msgUrl, args.msgVpnName, app)
        write_sdk_subscribers(args.msgUrl, args.msgVpnName, app)



    write_sdk_publish_run_all()
    write_sdk_subscribe_run_all()
    print(apps_dict)


    return None


if __name__ == "__main__":
    http_client.HTTPConnection.debuglevel = 1
    logging.basicConfig(level=logging.INFO)
    requests_log = logging.getLogger("requests.packages.urllib3")
    requests_log.setLevel(logging.DEBUG)
    requests_log.propagate = True
    # disable warning messages about https connection
    urllib3.disable_warnings()
    main(sys.argv[1:])