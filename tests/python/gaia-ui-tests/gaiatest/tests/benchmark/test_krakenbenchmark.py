# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

import re
import json
import codecs

from marionette import By
from marionette import Wait
from marionette.errors import NoSuchElementException
from marionette.errors import StaleElementException

from gaiatest import GaiaTestCase
from gaiatest.apps.browser.app import Browser


class TestBrowserKrakenbenchmark(GaiaTestCase):

    _output_csv_filename = 'krakenbenchmark.csv'
    _output_json_filename = 'krakenbenchmark.json'
    _start_button_locator = (By.CSS_SELECTOR, 'div#results a')
    _result_text_locator = (By.CSS_SELECTOR, 'pre#console')
    _result_url_locator = (By.ID, 'selfUrl')

    def setUp(self):
        GaiaTestCase.setUp(self)
        self.connect_to_network()
        self.test_url = 'http://krakenbenchmark.mozilla.org'

    def test_browser_krakenbenchmark(self):
        """
        Kraken JavaScripte Benchmark Test
        http://krakenbenchmark.mozilla.org
        """

        browser = Browser(self.marionette)
        browser.launch()
        browser.go_to_url(self.test_url)
        browser.switch_to_content()

        ## Launch
        Wait(self.marionette).until(lambda m: 'Kraken JavaScript Benchmark' in m.title)

        ## Start
        link = self.marionette.find_element(*self._start_button_locator)
        self.marionette.execute_script('arguments[0].scrollIntoView(false);', [link])
        link.tap()

        ## In progress
        Wait(self.marionette).until(lambda m: 'In Progress' in m.title)
        print '\nIn Progress...\n'

        ## Wait for finish
        Wait(self.marionette, timeout=30*60).until(lambda m: 'Results' in m.title)

        ## Get the results
        self.wait_for_element_displayed(*self._result_text_locator)
        results = self.marionette.find_element(*self._result_text_locator)
        print '\n', results.text

        ## Parsing for output CSV file
        f_csv = codecs.open(self._output_csv_filename, 'w', 'utf8')
        csv_key_column = ''
        csv_value_column = ''
        console_results_list = results.text.split('\n')
        for result in console_results_list:
            if 'ms' not in result:
                pass
            else:
                m = re.match(r"\s*(?P<key>\S+):\s+(?P<time_ms>\d+\.\d+)ms\s+\+\/\-\s+(?P<CI_95>\d+\.\d+)\%", result)
                if len(csv_key_column) > 0:
                    csv_key_column = csv_key_column + ',"' + m.group('key') + '"'
                    csv_value_column = csv_value_column + ',"' + m.group('time_ms') + '"'
                else:
                    csv_key_column = '"' + m.group('key') + '"'
                    csv_value_column = '"' + m.group('time_ms') + '"'
        f_csv.write('%s\n%s\n' % (csv_key_column, csv_value_column))
        f_csv.close()

        ## Parsing for JSON object (Datazilla)
        f_json = codecs.open(self._output_json_filename, 'w', 'utf8')
        result_url = self.marionette.find_element(*self._result_url_locator).get_attribute('value')
        results_list = re.findall(r'\%22\S+?\%22:\%5B[\d+,]*\d+', re.sub(r'^http:.+\%20', '', result_url))
        results_dict = {}
        for result in results_list:
            m = re.match(r'\%22(?P<key>\S+?)\%22:\%5B(?P<values>[\d+,]*\d+)', result)
            results_dict[m.group('key')] = m.group('values').split(',')
        results_json = json.dumps(results_dict, sort_keys=True, indent=4)
        f_json.write(results_json)
        f_json.close()

    def wait_for_element_displayed(self, by, locator, timeout=None):
        Wait(self.marionette, timeout, ignored_exceptions=[NoSuchElementException, StaleElementException]).until(
            lambda m: m.find_element(by, locator).is_displayed())
