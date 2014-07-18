#!/usr/bin/env python
#
# How to submit test results to Datazilla:
# 1) Attach a b2g device with an engineering build
# 2) Issue 'adb forward tcp:2828 tcp:2828' cmd
# 3) Run test, log the resultes into results file by JSON format
# 4) Keep the device connected, and turn on wifi (so device can get a macAddress), then
# 5) Run this script and provide the command line options/values, without '--submit'
# 6) Review the results as displayed in the console, verify
# 7) To submit the results, repeat the cmd but use '--submit'

import os
import json
from optparse import OptionParser
from urlparse import urlparse

import dzclient
import mozdevice
import mozversion
import gaiatest
from marionette import Marionette


class DatazillaPerfPoster(object):

    def __init__(self, marionette, datazilla_config=None, sources=None, device_serial=None):
        self.marionette = marionette
        self.device_serial = device_serial

        settings = gaiatest.GaiaData(self.marionette).all_settings  # get all settings
        mac_address = self.marionette.execute_script('return navigator.mozWifiManager && navigator.mozWifiManager.macAddress;')

        self.submit_report = True
        self.ancillary_data = {}

        if gaiatest.GaiaDevice(self.marionette).is_android_build:
            # get gaia, gecko and build revisions
            device_manager = mozdevice.DeviceManagerADB(deviceSerial=self.device_serial)
            version = mozversion.get_version(dm_type='adb', device_serial=self.device_serial)
            self.ancillary_data['build_revision'] = version.get('build_changeset')
            self.ancillary_data['gaia_revision'] = version.get('gaia_changeset')
            self.ancillary_data['gecko_repository'] = version.get('application_repository')
            self.ancillary_data['gecko_revision'] = version.get('application_changeset')
            self.ancillary_data['ro.build.version.incremental'] = version.get('device_firmware_version_incremental')
            self.ancillary_data['ro.build.version.release'] = version.get('device_firmware_version_release')
            self.ancillary_data['ro.build.date.utc'] = version.get('device_firmware_date')

        self.required = {
            'gaia_revision': self.ancillary_data.get('gaia_revision'),
            'gecko_repository': self.ancillary_data.get('gecko_repository'),
            'gecko_revision': self.ancillary_data.get('gecko_revision'),
            'build_revision': self.ancillary_data.get('build_revision'),
            'protocol': datazilla_config['protocol'],
            'host': datazilla_config['host'],
            'project': datazilla_config['project'],
            'branch': datazilla_config['branch'],
            'oauth_key': datazilla_config['oauth_key'],
            'oauth_secret': datazilla_config['oauth_secret'],
            'machine_name': datazilla_config['machine_name'] or mac_address,
            'device_name': datazilla_config['device_name'],
            'os_version': settings.get('deviceinfo.os'),
            'id': settings.get('deviceinfo.platform_build_id')}

        for key, value in self.required.items():
            if not value:
                self.submit_report = False
                print '\nMissing required DataZilla field: %s' % key

        if not self.submit_report:
            print '\n***Reports will not be submitted to DataZilla***'

    def post_to_datazilla(self, results, app_name):
        # Prepare DataZilla results
        res = dzclient.DatazillaResult()
        test_suite = app_name.replace(' ', '_').lower()
        res.add_testsuite(test_suite)
        for metric in results.keys():
            res.add_test_results(test_suite, metric, results[metric])
        req = dzclient.DatazillaRequest(
            protocol=self.required.get('protocol'),
            host=self.required.get('host'),
            project=self.required.get('project'),
            oauth_key=self.required.get('oauth_key'),
            oauth_secret=self.required.get('oauth_secret'),
            machine_name=self.required.get('machine_name'),
            os='Firefox OS',
            os_version=self.required.get('os_version'),
            platform='Gonk',
            build_name='B2G',
            version='prerelease',
            revision=self.ancillary_data.get('gaia_revision'),
            branch=self.required.get('branch'),
            id=self.required.get('id'))

        # Send DataZilla results
        req.add_datazilla_result(res)
        for dataset in req.datasets():
            dataset['test_build'].update(self.ancillary_data)
            dataset['test_machine'].update({'type': self.required.get('device_name')})
            print '\nSubmitting results to DataZilla: %s' % dataset
            response = req.send(dataset)
            print 'Response: %s\n' % response.read()


class dzOptionParser(OptionParser):
    def __init__(self, **kwargs):
        OptionParser.__init__(self, **kwargs)
        self.add_option('--file',
                        action='store',
                        dest='results_file',
                        metavar='str',
                        help='JSON results file from the test')
        self.add_option('--device-serial',
                      action='store',
                      dest='device_serial',
                      metavar='str',
                      help='serial identifier of device to target')
        self.add_option('--dz-url',
                        action='store',
                        dest='datazilla_url',
                        default='https://datazilla.mozilla.org',
                        metavar='str',
                        help='datazilla server url (default: %default)')
        self.add_option('--dz-project',
                        action='store',
                        dest='datazilla_project',
                        metavar='str',
                        help='datazilla project name')
        self.add_option('--dz-branch',
                        action='store',
                        dest='datazilla_branch',
                        metavar='str',
                        help='datazilla branch name')
        self.add_option('--dz-device',
                        action='store',
                        dest='datazilla_device_name',
                        metavar='str',
                        help='datazilla device name')  
        self.add_option('--dz-machine',
                        action='store',
                        dest='datazilla_machine_name',
                        metavar='str',
                        help='datazilla machine name')
        self.add_option('--dz-suite',
                        action='store',
                        dest='datazilla_test_suite',
                        metavar='str',
                        help='datazilla test suite')
        self.add_option('--dz-key',
                        action='store',
                        dest='datazilla_key',
                        metavar='str',
                        help='oauth key for datazilla server')
        self.add_option('--dz-secret',
                        action='store',
                        dest='datazilla_secret',
                        metavar='str',
                        help='oauth secret for datazilla server')
#        self.add_option('--sources',
#                        action='store',
#                        dest='sources',
#                        metavar='str',
#                        help='Optional path to sources.xml containing project revisions')
        self.add_option('--submit',
                        action='store_true',
                        dest='send_to_datazilla',
                        help='Send results to datazilla')

    def datazilla_config(self, options):
        datazilla_url = urlparse(options.datazilla_url)
        datazilla_config = {
            'protocol': datazilla_url.scheme,
            'host': datazilla_url.hostname,
            'project': options.datazilla_project,
            'branch': options.datazilla_branch,
            'device_name': options.datazilla_device_name,
            'machine_name': options.datazilla_machine_name,
            'oauth_key': options.datazilla_key,
            'oauth_secret': options.datazilla_secret}
        return datazilla_config


def cli():
    parser = dzOptionParser(usage='%prog file [options]')
    options, args = parser.parse_args()

    # Ensure have all required options
    if (not options.datazilla_project or not options.datazilla_branch
        or not options.datazilla_key or not options.datazilla_secret or not options.datazilla_test_suite):
        parser.print_help()
        print 'please specify the information of Datazilla...'
        parser.exit()

    # Either a single file or option to process all in given folder
    if (not options.results_file):
        parser.print_help()
        print 'please specify the result file...'
        parser.exit()

    # Ensure results file actually exists
    if options.results_file:
        if not os.path.exists(options.results_file):
            raise Exception('%s file does not exist' %options.results_file)
        
    # Parse config options
    datazilla_config = parser.datazilla_config(options)

    # Start marionette session
    marionette = Marionette(host='localhost', port=2828)  # TODO command line option for address
    marionette.start_session()

    # Create datazilla post object
    poster = DatazillaPerfPoster(marionette, datazilla_config=datazilla_config, sources=None)

    # If was an error getting required values then poster.submit_report will be false;
    # if it is true then ok to submit if user wants to
    if poster.submit_report:
        if not options.send_to_datazilla:
            poster.submit_report = False

    # Parse checkpoint results from result file
    print "\nProcessing results in '%s'\n" % options.results_file
    results_file = open(options.results_file, 'r')
    results = json.loads(results_file.read())
    results_file.close()

    # Display the Datazilla configuration
    print 'Datazilla configuration:'
    for key, value in poster.required.items():
        print key + ":", value

    # Submit or print the results
    if poster.submit_report:
        poster.post_to_datazilla(results, options.datazilla_test_suite)
    else:
        print '\nSubmitting test results data:\n'
        print results
        print "\nTo submit results, fix any missing fields and use the '--submit' option.\n"


if __name__ == '__main__':
    cli()
