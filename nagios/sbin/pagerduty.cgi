#!/usr/bin/env perl

use warnings;
use strict;

use CGI;
use JSON;
use LWP::UserAgent;

# =============================================================================

my $CONFIG = {
	# Nagios/Ubuntu defaults
	'command_file' => '/usr/local/nagios/var/rw/nagios.cmd', # External commands file
	# Icinga/CentOS defaults
	#'command_file' => '/var/spool/icinga/cmd/icinga.cmd', # External commands file
	# Icinga acknowledgement TTL
	'ack_ttl' => 0, # Time in seconds the acknowledgement in Icinga last before
	                # it times out automatically. 0 means the acknowledgement
	                # never expires. If you're using Nagios this MUST be 0.
};

# =============================================================================

sub ackHost {
	my ($time, $host, $comment, $author, $sticky, $notify, $persistent) = @_;

	# Open the external commands file
	if (! open (NAGIOS, '>>', $CONFIG->{'command_file'})) {
		# Well shizzle
		return (undef, $!);
	}

	# Success! Write the command
	if ($CONFIG->{'ack_ttl'} <= 0) {
		printf (NAGIOS "[%u] ACKNOWLEDGE_HOST_PROBLEM;%s;%u;%u;%u;%s;%s\n", $time, $host, $sticky, $notify, $persistent, $author, $comment);

	} else {
		printf (NAGIOS "[%u] ACKNOWLEDGE_HOST_PROBLEM_EXPIRE;%s;%u;%u;%u;%u;%s;%s\n", $time, $host, $sticky, $notify, $persistent, ($time + $CONFIG->{'ack_ttl'}), $author, $comment);
	}
	# Close the file handle
	close (NAGIOS);

	# Return with happiness
	return (1, undef);
}

# =============================================================================

sub deackHost {
	my ($time, $host) = @_;

	# Open the external commands file
	if (! open (NAGIOS, '>>', $CONFIG->{'command_file'})) {
		# Well shizzle
		return (undef, $!);
	}

	# Success! Write the command
	printf (NAGIOS "[%u] REMOVE_HOST_ACKNOWLEDGEMENT;%s\n", $time, $host);
	# Close the file handle
	close (NAGIOS);

	# Return with happiness
	return (1, undef);
}

# =============================================================================

sub ackService {
	my ($time, $host, $service, $comment, $author, $sticky, $notify, $persistent) = @_;

	# Open the external commands file
	if (! open (NAGIOS, '>>', $CONFIG->{'command_file'})) {
		# Well shizzle
		return (undef, $!);
	}

	# Success! Write the command
	if ($CONFIG->{'ack_ttl'} <= 0) {
		printf (NAGIOS "[%u] ACKNOWLEDGE_SVC_PROBLEM;%s;%s;%u;%u;%u;%s;%s\n", $time, $host, $service, $sticky, $notify, $persistent, $author, $comment);

	} else {
		printf (NAGIOS "[%u] ACKNOWLEDGE_SVC_PROBLEM_EXPIRE;%s;%s;%u;%u;%u;%u;%s;%s\n", $time, $host, $service, $sticky, $notify, $persistent, ($time + $CONFIG->{'ack_ttl'}), $author, $comment);
	}

	# Close the file handle
	close (NAGIOS);

	# Return with happiness
	return (1, undef);
}

# =============================================================================

sub deackService {
	my ($time, $host, $service) = @_;

	# Open the external commands file
	if (! open (NAGIOS, '>>', $CONFIG->{'command_file'})) {
		# Well shizzle
		return (undef, $!);
	}

	# Success! Write the command
	printf (NAGIOS "[%u] REMOVE_SVC_ACKNOWLEDGEMENT;%s;%s\n", $time, $host, $service);
	# Close the file handle
	close (NAGIOS);

	# Return with happiness
	return (1, undef);
}

# =============================================================================

my ($TIME, $QUERY, $POST, $JSON);

$TIME = time ();

$QUERY = CGI->new ();

if (! defined ($POST = $QUERY->param ('POSTDATA'))) {
	print ("Status: 400 Requests must be POSTs\n\n400 Requests must be POSTs\n");
	exit (0);
}

if (! defined ($JSON = JSON->new ()->utf8 ()->decode ($POST))) {
	print ("Status: 400 Request payload must be JSON blob\n\n400 Request payload must JSON blob\n");
	exit (0);
}

if ((ref ($JSON) ne 'HASH') || ! defined ($JSON->{'messages'}) || (ref ($JSON->{'messages'}) ne 'ARRAY')) {
	print ("Status: 400 JSON blob does not match the expected format\n\n400 JSON blob does not match expected format\n");
	exit (0);
}

my ($message, $return);
$return = {
	'status' => 'okay',
	'messages' => {}
};

MESSAGE: foreach $message (@{$JSON->{'messages'}}) {
	my ($hostservice, $status, $error);

	if ((ref ($message) ne 'HASH') || ! defined ($message->{'type'})) {
		next MESSAGE;
	}

	$hostservice = $message->{'data'}->{'incident'}->{'trigger_summary_data'};

	if (! defined ($hostservice)) {
		next MESSAGE;
	}

	if ($message->{'type'} eq 'incident.acknowledge') {
                if ($hostservice->{'SERVICEDESC'} eq "") {
			($status, $error) = ackHost ($TIME, $hostservice->{'HOSTNAME'}, 'Acknowledged by PagerDuty', 'PagerDuty', 2, 0, 0);

		} else {
			($status, $error) = ackService ($TIME, $hostservice->{'HOSTNAME'}, $hostservice->{'SERVICEDESC'}, 'Acknowledged by PagerDuty', 'PagerDuty', 2, 0, 0);
		}

		$return->{'messages'}{$message->{'id'}} = {
			'status' => ($status ? 'okay' : 'fail'),
			'message' => ($error ? $error : undef)
		};

	} elsif ($message->{'type'} eq 'incident.unacknowledge') {
		if (! defined ($hostservice->{'SERVICEDESC'})) {
			($status, $error) = deackHost ($TIME, $hostservice->{'HOSTNAME'});

		} else {
			($status, $error) = deackService ($TIME, $hostservice->{'HOSTNAME'}, $hostservice->{'SERVICEDESC'});
		}

		$return->{'messages'}->{$message->{'id'}} = {
			'status' => ($status ? 'okay' : 'fail'),
			'message' => ($error ? $error : undef)
		};
		$return->{'status'} = ($status eq 'okay' ? $return->{'status'} : 'fail');
	}
}

printf ("Status: 200 Okay\nContent-type: application/json\n\n%s\n", JSON->new ()->utf8 ()->encode ($return));
