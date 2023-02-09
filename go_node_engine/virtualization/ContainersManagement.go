package virtualization

import (
	"bytes"
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"github.com/containerd/containerd"
	"github.com/containerd/containerd/cio"
	"github.com/containerd/containerd/containers"
	"github.com/containerd/containerd/contrib/nvidia"
	"github.com/containerd/containerd/namespaces"
	"github.com/containerd/containerd/oci"
	"github.com/opencontainers/runtime-spec/specs-go"
	"github.com/struCoder/pidusage"
	"go_node_engine/logger"
	"go_node_engine/model"
	"go_node_engine/requests"
	"os"
	"reflect"
	"strconv"
	"strings"
	"sync"
	"time"
)

type ContainerRuntime struct {
	contaierClient *containerd.Client
	serviceList    map[string]*model.Service
	channelLock    *sync.RWMutex
	ctx            context.Context
}

var runtime = ContainerRuntime{
	channelLock: &sync.RWMutex{},
}

var containerdSingletonCLient sync.Once
var startContainerMonitoring sync.Once

const NAMESPACE = "oakestra"

type HealthStatus int64

const (
	HEALTHY HealthStatus = iota
	UNHEALTHY
	ERROR
)

func GetContainerdClient() *ContainerRuntime {
	containerdSingletonCLient.Do(func() {
		client, err := containerd.New("/run/containerd/containerd.sock")
		if err != nil {
			logger.ErrorLogger().Fatalf("Unable to start the container engine: %v\n", err)
		}
		runtime.contaierClient = client
		runtime.serviceList = make(map[string]*model.Service)
		runtime.ctx = namespaces.WithNamespace(context.Background(), NAMESPACE)
		runtime.forceContainersCleanup()
	})
	return &runtime
}

func (r *ContainerRuntime) StopContainerdClient() {
	r.channelLock.Lock()
	taskIDs := reflect.ValueOf(r.serviceList).MapKeys()
	r.channelLock.Unlock()

	for _, taskid := range taskIDs {
		err := r.Undeploy(extractSnameFromTaskID(taskid.String()), extractInstanceNumberFromTaskID(taskid.String()))
		if err != nil {
			logger.ErrorLogger().Printf("Unable to undeploy %s, error: %v", taskid.String(), err)
		}
	}
	r.contaierClient.Close()
}

func (r *ContainerRuntime) Deploy(service *model.Service, statusChangeNotificationHandler func(service model.Service)) error {

	var image containerd.Image
	logger.CsvLog(logger.DEPLOYREQUEST, genTaskID(service.Sname, service.Instance), "")
	// pull the given image
	sysimg, err := r.contaierClient.ImageService().Get(r.ctx, service.Image)
	if err == nil {
		image = containerd.NewImage(r.contaierClient, sysimg)
	} else {
		logger.ErrorLogger().Printf("Error retrieving the image: %v \n Trying to pull the image online.", err)

		image, err = r.contaierClient.Pull(r.ctx, service.Image, containerd.WithPullUnpack)
		if err != nil {
			return err
		}
	}

	killChannel := make(chan bool, 1)
	startupChannel := make(chan bool, 0)
	errorChannel := make(chan error, 0)

	r.channelLock.RLock()
	el, servicefound := r.serviceList[genTaskID(service.Sname, service.Instance)]
	r.channelLock.RUnlock()
	if !servicefound || el == nil {
		r.channelLock.Lock()
		service.KillChan = &killChannel
		r.serviceList[genTaskID(service.Sname, service.Instance)] = service
		r.channelLock.Unlock()
	} else {
		return errors.New("Service already deployed")
	}

	// create startup routine which will accompany the container through its lifetime
	go r.containerCreationRoutine(
		r.ctx,
		image,
		service,
		startupChannel,
		errorChannel,
		&killChannel,
		statusChangeNotificationHandler,
	)

	// wait for updates regarding the container creation
	if <-startupChannel != true {
		return <-errorChannel
	}

	return nil
}

func (r *ContainerRuntime) Undeploy(service string, instance int) error {
	logger.CsvLog(logger.UNDEPLOYREQUEST, genTaskID(service, instance), "")
	r.channelLock.Lock()
	defer r.channelLock.Unlock()
	taskid := genTaskID(service, instance)
	el, found := r.serviceList[taskid]
	if found && el != nil {
		logger.InfoLogger().Printf("Sending kill signal to %s", taskid)
		*r.serviceList[taskid].KillChan <- true
		select {
		case res := <-*r.serviceList[taskid].KillChan:
			if res == false {
				logger.ErrorLogger().Printf("Unable to stop service %s", taskid)
				return errors.New("Unable to stop service")
			}
			delete(r.serviceList, taskid)
			return nil
		case <-time.After(5 * time.Second):
			logger.ErrorLogger().Printf("Unable to stop service, timeout %s", taskid)
			return errors.New("UnDeployment timeout")
		}
	} else {
		r.forceContainerCleanup(taskid)
	}
	return errors.New("service not found, triggered forced cleanup")
}

func (r *ContainerRuntime) containerCreationRoutine(
	ctx context.Context,
	image containerd.Image,
	service *model.Service,
	startup chan bool,
	errorchan chan error,
	killChannel *chan bool,
	statusChangeNotificationHandler func(service model.Service),
) {

	hostname := genTaskID(service.Sname, service.Instance)

	revert := func(err error) {
		startup <- false
		errorchan <- err
		r.channelLock.Lock()
		defer r.channelLock.Unlock()
		r.serviceList[hostname] = nil
	}

	//create container general oci specs
	specOpts := []oci.SpecOpts{
		oci.WithImageConfig(image),
		oci.WithHostHostsFile,
		oci.WithHostname(hostname),
		oci.WithEnv(append([]string{fmt.Sprintf("HOSTNAME=%s", hostname)}, service.Env...)),
	}

	//add user defined commands
	if len(service.Commands) > 0 {
		specOpts = append(specOpts, oci.WithProcessArgs(service.Commands...))
	}

	//add GPU if needed
	if service.Vgpus > 0 {
		specOpts = append(specOpts, nvidia.WithGPUs(nvidia.WithAllDevices, nvidia.WithAllCapabilities))
		logger.InfoLogger().Printf("NVIDIA - Adding GPU driver")
	}
	//add resolve file with default google dns
	resolvconfFile, err := getGoogleDNSResolveConf()
	if err != nil {
		revert(err)
		return
	}
	defer resolvconfFile.Close()
	_ = resolvconfFile.Chmod(444)
	specOpts = append(specOpts, withCustomResolvConf(resolvconfFile.Name()))

	// create the container
	container, err := r.contaierClient.NewContainer(
		ctx,
		hostname,
		containerd.WithImage(image),
		containerd.WithNewSnapshot(fmt.Sprintf("%s", hostname), image),
		containerd.WithNewSpec(specOpts...),
	)
	if err != nil {
		revert(err)
		return
	}

	//	generate task
	logfile := logger.GetServiceLogfile(hostname)
	task, err := container.NewTask(ctx, cio.NewCreator(cio.WithStreams(nil, logfile, logfile)))
	if err != nil {
		logger.ErrorLogger().Printf("ERROR: containerd task creation failure: %v", err)
		_ = container.Delete(ctx)
		revert(err)
		return
	}

	// defer cleanup function
	defer func() {
		logger.CsvLog(logger.DEAD, hostname, "")
		_ = killTaskAndContainer(ctx, task, container)
		//removing from killqueue
		r.channelLock.Lock()
		defer r.channelLock.Unlock()
		r.serviceList[hostname] = nil
		//detaching network
		if model.GetNodeInfo().Overlay {
			_ = requests.DetachNetworkFromTask(service.Sname, service.Instance)
		}
		//notify dead
		service.Status = model.SERVICE_FAILED
		statusChangeNotificationHandler(*service)
		*killChannel <- true
		r.removeContainer(container)
	}()

	// get wait channel
	exitStatusC, err := task.Wait(ctx)
	if err != nil {
		logger.ErrorLogger().Printf("ERROR: containerd task wait failure: %v", err)
		revert(err)
		return
	}

	// if Overlay mode is active then attach network to the task
	if err := r.attachNetwork(task, *service); err != nil {
		logger.ErrorLogger().Printf("Unable to attach network interface to the task: %v", err)
		revert(err)
	}

	// execute the image's task
	if err := task.Start(ctx); err != nil {
		logger.ErrorLogger().Printf("ERROR: containerd task start failure: %v", err)
		revert(err)
		return
	}

	service.Status = model.SERVICE_CREATING
	startup <- true
	logger.CsvLog(logger.DEPLOYED, hostname, "")

	// execute healthcheck
	go func() {
		for service.Status != model.SERVICE_ACTIVE {
			health, err := r.executeHealthCheck(ctx, container, *service)
			if health == UNHEALTHY {
				logger.ErrorLogger().Printf("ERROR: Health check failed with error: %v", err)
				time.Sleep(time.Millisecond * 200)
				continue
			}
			if health == ERROR {
				logger.ErrorLogger().Printf("ERROR:%v", err)
				revert(err)
				return
			}
			if health == HEALTHY {
				service.Status = model.SERVICE_ACTIVE
			}
		}
	}()

	// wait for manual task kill or task finish
	select {
	case exitStatus := <-exitStatusC:
		//TODO: container exited, do something, notify to cluster manager
		logger.InfoLogger().Printf("WARNING: Container exited with status %d", exitStatus.ExitCode())
		logger.CsvLog(logger.DEAD, service.Sname, fmt.Sprintf("{'status': %d}", exitStatus.ExitCode()))
		service.StatusDetail = fmt.Sprintf("Container exited with status: %d", exitStatus.ExitCode())
	case <-*killChannel:
		logger.InfoLogger().Printf("Kill channel message received for task %s", task.ID())
	}
}

func (r *ContainerRuntime) ResourceMonitoring(every time.Duration, notifyHandler func(res []model.Resources)) {
	//start container monitoring service
	startContainerMonitoring.Do(func() {
		for true {
			select {
			case <-time.After(every):
				deployedContainers, err := r.contaierClient.Containers(r.ctx)
				if err != nil {
					logger.ErrorLogger().Printf("Unable to fetch running containers: %v", err)
				}
				resourceList := make([]model.Resources, 0)
				for _, container := range deployedContainers {
					task, err := container.Task(r.ctx, nil)
					if err != nil {
						logger.ErrorLogger().Printf("Unable to fetch container task: %v", err)
						continue
					}
					sysInfo, err := pidusage.GetStat(int(task.Pid()))
					if err != nil {
						logger.ErrorLogger().Printf("Unable to fetch task info: %v", err)
						continue
					}
					containerMetadata, err := container.Info(r.ctx)
					if err != nil {
						logger.ErrorLogger().Printf("Unable to fetch container metadata: %v", err)
						continue
					}
					currentsnapshotter := r.contaierClient.SnapshotService(containerd.DefaultSnapshotter)
					usage, err := currentsnapshotter.Usage(r.ctx, containerMetadata.SnapshotKey)
					if err != nil {
						logger.ErrorLogger().Printf("Unable to fetch task disk usage: %v", err)
						continue
					}
					el, found := r.serviceList[task.ID()]
					if found && el != nil {
						if el.Status != model.SERVICE_ACTIVE {
							logger.InfoLogger().Printf("Service %s not ACTIVE, service info skipped", task.ID())
							continue
						}
					}

					resourceList = append(resourceList, model.Resources{
						Cpu:      fmt.Sprintf("%f", sysInfo.CPU),
						Memory:   fmt.Sprintf("%f", sysInfo.Memory),
						Disk:     fmt.Sprintf("%d", usage.Size),
						Sname:    extractSnameFromTaskID(task.ID()),
						Pid:      task.Pid(),
						Runtime:  model.CONTAINER_RUNTIME,
						Instance: extractInstanceNumberFromTaskID(task.ID()),
					})
					resourcesJson, _ := json.Marshal(resourceList)
					logger.CsvLog(logger.SERVICE_RESOURCES, task.ID(), string(resourcesJson))
				}
				//NOTIFY WITH THE CURRENT CONTAINERS STATUS
				notifyHandler(resourceList)
			}
		}
	})
}

func (r *ContainerRuntime) forceContainersCleanup() {
	deployedContainers, err := r.contaierClient.Containers(r.ctx)
	if err != nil {
		logger.ErrorLogger().Printf("Unable to fetch running containers: %v", err)
	}
	for _, container := range deployedContainers {
		r.removeContainer(container)
	}
}

func (r *ContainerRuntime) forceContainerCleanup(id string) {
	deployedContainers, err := r.contaierClient.Containers(r.ctx)
	if err != nil {
		logger.ErrorLogger().Printf("Unable to fetch running containers: %v", err)
	}
	for _, container := range deployedContainers {
		if container.ID() == id {
			r.removeContainer(container)
		}
	}
}

func (r *ContainerRuntime) removeContainer(container containerd.Container) {
	logger.InfoLogger().Printf("Clenaning up container: %s", container.ID())
	task, err := container.Task(r.ctx, nil)
	if err != nil {
		logger.ErrorLogger().Printf("Unable to fetch container task: %v", err)
	}
	if err == nil {
		err = killTaskAndContainer(r.ctx, task, container)
		if err != nil {
			logger.ErrorLogger().Printf("Unable to fetch kill task: %v", err)
		}
	}
	err = container.Delete(r.ctx)
	if err != nil {
		logger.ErrorLogger().Printf("Unable to delete container: %v", err)
	}
}

func withCustomResolvConf(src string) func(context.Context, oci.Client, *containers.Container, *oci.Spec) error {
	return func(_ context.Context, _ oci.Client, _ *containers.Container, s *oci.Spec) error {
		s.Mounts = append(s.Mounts, specs.Mount{
			Destination: "/etc/resolv.conf",
			Type:        "bind",
			Source:      src,
			Options:     []string{"rbind", "ro"},
		})
		return nil
	}
}

func getGoogleDNSResolveConf() (*os.File, error) {
	file, err := os.CreateTemp("/tmp", "edgeio-resolv-conf")
	if err != nil {
		logger.ErrorLogger().Printf("Unable to create temp resolv file: %v", err)
		return nil, err
	}
	_, err = file.WriteString(fmt.Sprintf("nameserver 8.8.8.8\n"))
	if err != nil {
		logger.ErrorLogger().Printf("Unable to write temp resolv file: %v", err)
		return nil, err
	}
	return file, err
}

func killTaskAndContainer(ctx context.Context, task containerd.Task, container containerd.Container) error {

	if err := killTask(ctx, task); err != nil {
		return err
	}
	_ = container.Delete(ctx)

	logger.ErrorLogger().Printf("Task %s terminated", task.ID())
	return nil
}

func killTask(ctx context.Context, task containerd.Task) error {
	//removing the task
	p, err := task.LoadProcess(ctx, task.ID(), nil)
	if err != nil {
		logger.ErrorLogger().Printf("ERROR deleting the task, LoadProcess: %v", err)
		return err
	}
	_, err = p.Delete(ctx, containerd.WithProcessKill)
	if err != nil {
		logger.ErrorLogger().Printf("ERROR deleting the task, Delete: %v", err)
		return err
	}
	_, _ = task.Delete(ctx)
	return nil
}

func extractSnameFromTaskID(taskid string) string {
	sname := taskid
	index := strings.LastIndex(taskid, ".instance")
	if index > 0 {
		sname = taskid[0:index]
	}
	return sname
}

func extractInstanceNumberFromTaskID(taskid string) int {
	instance := 0
	separator := ".instance"
	index := strings.LastIndex(taskid, separator)
	if index > 0 {
		number, err := strconv.Atoi(taskid[index+len(separator)+1:])
		if err == nil {
			instance = number
		}
	}
	return instance
}

func genTaskID(sname string, instancenumber int) string {
	return fmt.Sprintf("%s.instance.%d", sname, instancenumber)
}

// attach network only if overlay mode active, otherwise it does nothing
func (r *ContainerRuntime) attachNetwork(task containerd.Task, service model.Service) error {
	if model.GetNodeInfo().Overlay {
		taskpid := int(task.Pid())
		err := requests.AttachNetworkToTask(taskpid, service.Sname, service.Instance, service.Ports)
		if err != nil {
			return err
		}
	}
	return nil
}

// return the status of the healthce
func (r *ContainerRuntime) executeHealthCheck(ctx context.Context, container containerd.Container, service model.Service) (HealthStatus, error) {

	//if no health check defined then skip
	if service.HealthCheck == nil || len(service.HealthCheck) == 0 {
		return HEALTHY, nil
	}

	//create healthcheck task process specs
	spec, err := container.Spec(ctx)
	if err != nil {
		return ERROR, err
	}
	pspec := spec.Process
	pspec.Args = service.HealthCheck

	//retrieve container task
	task, err := container.Task(ctx, nil)
	if err != nil {
		return ERROR, err
	}

	//create io for the healthcheck task
	healthbuffer := new(bytes.Buffer)
	ioCreator := cio.NewCreator(cio.WithStreams(nil, healthbuffer, healthbuffer))

	//create and execute health check task
	process, err := task.Exec(ctx, fmt.Sprintf("%s.%d-health-check", service.Sname, service.Instance), pspec, ioCreator)
	if err != nil {
		return ERROR, err
	}
	exitstatus, err := process.Wait(ctx)
	if err != nil {
		return ERROR, err
	}
	if err := process.Start(ctx); err != nil {
		return ERROR, err
	}

	//wait health-check to end
	exit := <-exitstatus
	_, _ = process.Delete(ctx)

	if err != nil {
		return 0, err
	}

	//if health check result == 1 then success
	if exit.ExitCode() > 0 {
		return UNHEALTHY, errors.New(fmt.Sprintf("Health-check failed with exit code: %d and message: %s", exit.ExitCode(), healthbuffer.String()))
	}
	return HEALTHY, nil
}
