package env

import (
	"errors"
	"github.com/tkanos/gonfig"
	"log"
	"net"
	"os/exec"
	"strconv"
	"strings"
)

// Return errors
const NamespaceAlreadyDeclared string = "namespace already declared"

// Config
type Configuration struct {
	HostBridgeName             string
	HostBridgeIP               string
	HostBridgeMask             string
	HostTunName                string
	ConnectedInternetInterface string
}

// env class
type Environment struct {
	nodeNetwork       net.IPNet
	nameSpaces        []string
	networkInterfaces []networkInterface
	nextVethNumber    int
	proxyName         string
	config            Configuration
}

// current network interfaces in the system
type networkInterface struct {
	number                   int
	veth0                    string
	veth0ip                  net.IP
	veth1                    string
	veth1ip                  net.IP
	isConnectedToAnInterface bool
	interfaceNumber          int
	namespace                string
}

// environment constructor
func NewCustom(proxyname string, customConfig Configuration) Environment {
	e := Environment{
		nameSpaces:        make([]string, 0),
		networkInterfaces: make([]networkInterface, 0),
		nextVethNumber:    0,
		proxyName:         proxyname,
		config:            customConfig,
	}

	//create bridge
	log.Println("Creation of goProxyBridge")
	_, err := e.CreateHostBridge()
	if err != nil {
		log.Fatal(err.Error())
	}
	e.nextVethNumber = 0

	//enable IP forwarding
	log.Println("enabling IP forwarding")
	cmd := exec.Command("sysctl", "-w", "net.ipv4.ip_forward=1")
	_, err = cmd.Output()
	if err != nil {
		log.Fatal(err.Error())
	}

	//disable reverse path filtering
	cmd = exec.Command("echo", "0", ">", "/proc/sys/net/ipv4/conf/"+e.config.ConnectedInternetInterface+"/rp_filter")
	_, err = cmd.Output()
	if err != nil {
		log.Fatal(err.Error())
	}
	cmd = exec.Command("echo", "0", ">", "/proc/sys/net/ipv4/conf/"+e.config.HostBridgeName+"/rp_filter")
	_, err = cmd.Output()
	if err != nil {
		log.Fatal(err.Error())
	}

	//Enable tun device forwarding
	log.Println("enabling tun device forwarding")
	cmd = exec.Command("iptables", "-A", "FORWARD", "-i", e.config.HostBridgeName, "-o", proxyname, "-j", "ACCEPT")
	_, err = cmd.Output()
	if err != nil {
		log.Fatal(err.Error())
	}
	cmd = exec.Command("iptables", "-A", "FORWARD", "-o", e.config.HostBridgeName, "-i", proxyname, "-j", "ACCEPT")
	_, err = cmd.Output()
	if err != nil {
		log.Fatal(err.Error())
	}

	//update status with current network configuration
	log.Println("Reading the current environment configuration")
	err = e.Update()
	if err != nil {
		log.Fatal(err.Error())
	}

	return e
}

// Creates a new environment using the static configuration files
func NewStatic(proxyname string) Environment {
	log.Println("Loading config file for environment creation")
	config := Configuration{}
	//parse confgiuration file
	err := gonfig.GetConf("config/envcfg.json", &config)
	if err != nil {
		log.Fatal(err)
	}
	return NewCustom(proxyname, config)
}

// creates a new namespace and link it to the host bridge
// netname: short name representative of the namespace, better if a short unique name of the service, max 10 char
func (env *Environment) CreateNetworkNamespace(netname string, ip net.IP) (string, error) {
	//check if appName is valid
	for _, e := range env.nameSpaces {
		if e == netname {
			return "", errors.New(NamespaceAlreadyDeclared)
		}
	}

	//create namespace
	log.Println("creating namespace: " + netname)
	cmd := exec.Command("ip", "netns", "add", netname)
	_, err := cmd.Output()
	if err != nil {
		return "", err
	}

	//create veth pair to connect the namespace to the host bridge
	veth1name := "veth" + "00" + strconv.Itoa(env.nextVethNumber)
	veth2name := "veth" + "01" + strconv.Itoa(env.nextVethNumber)
	log.Println("creating veth pair: " + veth1name + "@" + veth2name)

	cleanup := func() {
		cmd := exec.Command("ip", "link", "delete", veth1name)
		_, _ = cmd.Output()
		cmd = exec.Command("ip", "netns", "delete", netname)
		_, _ = cmd.Output()
	}

	cmd = exec.Command("ip", "link", "add", veth1name, "type", "veth", "peer", "name", veth2name)
	_, err = cmd.Output()
	if err != nil {
		cleanup()
		return "", err
	}

	//attach veth2 to namespace
	log.Println("attaching " + veth2name + " to namespace " + netname)
	cmd = exec.Command("ip", "link", "set", veth2name, "netns", netname)
	_, err = cmd.Output()
	if err != nil {
		cleanup()
		return "", err
	}

	//assign ip to the namespace veth
	log.Println("assigning ip " + ip.String() + env.config.HostBridgeMask + " to " + veth2name)
	cmd = exec.Command("ip", "netns", "exec", netname, "ip", "addr", "add",
		ip.String()+env.config.HostBridgeMask, "dev", veth2name)
	//cmd = exec.Command("ip", "a", "add", ip.String(), "dev", veth2name)
	_, err = cmd.Output()
	if err != nil {
		cleanup()
		return "", err
	}

	//bring ns lo up
	log.Println("bringing lo up")
	cmd = exec.Command("ip", "netns", "exec", netname, "ip", "link", "set", "lo", "up")
	_, err = cmd.Output()
	if err != nil {
		cleanup()
		return "", err
	}

	//bring veth2 up
	log.Println("bringing " + veth2name + " up")
	cmd = exec.Command("ip", "netns", "exec", netname, "ip", "link", "set", veth2name, "up")
	_, err = cmd.Output()
	if err != nil {
		cleanup()
		return "", err
	}

	//attach veth1 to the bridge
	log.Println("attaching " + veth1name + " to host bridge")
	cmd = exec.Command("ip", "link", "set", veth1name, "master", env.config.HostBridgeName)
	_, err = cmd.Output()
	if err != nil {
		cleanup()
		return "", err
	}

	//bring veth1 up
	log.Println("bringing " + veth1name + " up")
	cmd = exec.Command("ip", "link", "set", veth1name, "up")
	_, err = cmd.Output()
	if err != nil {
		cleanup()
		return "", err
	}

	//add rules on netname namespace for routing through the veth
	log.Println("adding default routing rule inside " + netname)
	cmd = exec.Command("ip", "netns", "exec", netname, "ip", "route", "add", "default", "via", env.config.HostBridgeIP, "dev", veth2name)
	_, err = cmd.Output()
	if err != nil {
		cleanup()
		return "", err
	}

	//add rules on default namespace for routing to the new namespace
	log.Println("adding routing rule for default namespace to " + netname)
	cmd = exec.Command("ip", "route", "add", ip.String(), "via", env.config.HostBridgeIP)
	_, err = cmd.Output()
	if err != nil {
		cleanup()
		return "", err
	}

	//disable reverse path filtering
	log.Println("disabling reverse path filtering")
	cmd = exec.Command("echo", "0", ">", "/proc/sys/net/ipv4/conf/all/rp_filter")
	_, err = cmd.Output()
	if err != nil {
		log.Fatal(err.Error())
	}

	//add IP masquerade
	log.Println("add NAT ip MASQUERADING for the bridge")
	cmd = exec.Command("iptables", "-t", "nat", "-A", "POSTROUTING", "-s", ip.String()+env.config.HostBridgeMask, "-o", env.config.ConnectedInternetInterface, "-j", "MASQUERADE")
	_, err = cmd.Output()
	if err != nil {
		cleanup()
		return "", err
	}

	//add NAT packet forwarding rules
	log.Println("add NAT packet forwarding rules for " + netname)
	cmd = exec.Command("iptables", "-A", "FORWARD", "-o", env.config.ConnectedInternetInterface, "-i", veth1name, "-j", "ACCEPT")
	_, err = cmd.Output()
	if err != nil {
		cleanup()
		return "", err
	}
	cmd = exec.Command("iptables", "-A", "FORWARD", "-i", env.config.ConnectedInternetInterface, "-o", veth1name, "-j", "ACCEPT")
	_, err = cmd.Output()
	if err != nil {
		cleanup()
		return "", err
	}

	err = env.Update()
	if err != nil {
		cleanup()
		return "", err
	}

	return netname, nil
}

func (env *Environment) Destroy() {
	for _, ns := range env.nameSpaces {
		cmd := exec.Command("ip", "netns", "delete", ns)
		_, _ = cmd.Output()
	}
	cmd := exec.Command("ip", "link", "delete", env.config.HostBridgeName)
	_, _ = cmd.Output()
}

// update the env class with the current state of the machine. This method must be run always at boot
// updates current declared interfaces and namespaces
func (env *Environment) Update() error {

	// fetch current declared Namespaces
	netns := exec.Command("ip", "netns", "list")
	netnslines, err := netns.Output()
	if err != nil {
		return err
	}
	env.nameSpaces = NetworkNamespacesList(string(netnslines))

	// fetch current declared Veth pairs for default network namespace
	defaultNamespaceVeths, err := env.fetchNetworkVethLinkList("")
	if err != nil {
		return err
	}
	env.networkInterfaces = defaultNamespaceVeths

	nextVeth := 0

	// update next veth number
	for _, iface := range env.networkInterfaces {
		//if is one of the veths declared by us
		if strings.Contains(iface.veth0, "veth00") {
			// assign the next number bigger than the current declared veth
			vethnum, err := strconv.Atoi(strings.Replace(iface.veth0, "veth00", "", -1))
			if err == nil {
				if vethnum >= nextVeth {
					nextVeth = vethnum + 1
				}
			}
		}
	}
	env.nextVethNumber = nextVeth

	return nil
}

//given a namespace returns the veth delcard inside that namespace, empty string is the default namespace
func (env *Environment) fetchNetworkVethLinkList(namespace string) ([]networkInterface, error) {
	var linklines []byte
	var err error
	if namespace == "" {
		link := exec.Command("ip", "link", "list")
		linklines, err = link.Output()
	} else {
		link := exec.Command("ip", "netns", "exec", namespace, "ip", "link", "list")
		linklines, err = link.Output()
	}
	if err != nil {
		return nil, err
	}
	result := NetworkVethLinkList(string(linklines))

	for i := range result {
		elem := result[i]
		elem.namespace = namespace
		result[i] = elem
	}

	return result, nil
}

//create host bridge if it has not been created yet, return the current host bridge name or the newly created one
func (env *Environment) CreateHostBridge() (string, error) {
	//check current declared bridges
	bridgecmd := exec.Command("ip", "link", "list", "type", "bridge")
	bridgelines, err := bridgecmd.Output()
	if err != nil {
		return "", err
	}
	currentDeclaredBridges := extractNetInterfaceName(string(bridgelines))

	//is HostBridgeName already created?
	created := false
	for _, name := range currentDeclaredBridges {
		if name == env.config.HostBridgeName {
			created = true
		}
	}

	//if HostBridgeName exists already then return the name
	if created {
		return env.config.HostBridgeName, nil
	}

	//otherwise create it
	createbridgeCmd := exec.Command("ip", "link", "add", "name", env.config.HostBridgeName, "type", "bridge")
	_, err = createbridgeCmd.Output()
	if err != nil {
		return "", err
	}

	//assign ip to the bridge
	bridgeIpCmd := exec.Command("ip", "a", "add",
		env.config.HostBridgeIP+env.config.HostBridgeMask, "dev", env.config.HostBridgeName)
	_, err = bridgeIpCmd.Output()
	if err != nil {
		return "", err
	}

	//bring the bridge up
	bridgeUpCmd := exec.Command("ip", "link", "set", "dev", env.config.HostBridgeName, "up")
	_, err = bridgeUpCmd.Output()
	if err != nil {
		return "", err
	}

	//add iptables rule for forwarding packets
	iptablesCmd := exec.Command("iptables", "-A", "FORWARD", "-i", env.config.HostBridgeName, "-o",
		env.config.HostBridgeName, "-j", "ACCEPT")
	_, err = iptablesCmd.Output()
	if err != nil {
		return "", err
	}

	return env.config.HostBridgeName, nil
}

func nextIP(ip net.IP, inc uint) net.IP {
	i := ip.To4()
	v := uint(i[0])<<24 + uint(i[1])<<16 + uint(i[2])<<8 + uint(i[3])
	v += inc
	v3 := byte(v & 0xFF)
	v2 := byte((v >> 8) & 0xFF)
	v1 := byte((v >> 16) & 0xFF)
	v0 := byte((v >> 24) & 0xFF)
	return net.IPv4(v0, v1, v2, v3)
}
