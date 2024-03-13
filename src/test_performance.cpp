#include <exception>
#include <iostream>
#include "arv.h"

#include <string>
#include <iostream>
#include <sstream>
#include <vector>
#include <map>

#include <filesystem>
#include <iomanip>
#include <ctime>

#include <ion/ion.h>

#define LOG_DISPLAY true

void logWrite(std::string log_type, std::string msg){
    if(LOG_DISPLAY){
        std::cout << "[LOG " << __FILE__ << "]" << "[" << log_type << "] " << msg << std::endl;
    }
}

template<typename... Args>
void logInfo(Args... args) {
    std::ostringstream oss;
    (oss << ... << args);
    logWrite("INFO", oss.str()) ;
}

template<typename... Args>
void logWarning(Args... args) {
    std::ostringstream oss;
    (oss << ... << args);
    logWrite("WARNING", oss.str()) ;
}

template<typename... Args>
void logStatus(Args... args) {
    std::ostringstream oss;
    (oss << ... << args);
    logWrite("STATUS", oss.str()) ;
}

template <class T>
class UserOption {
    T value_;
    std::vector<std::string> keys_;
    std::string description_;

    public:
        UserOption(T value, std::vector<std::string>& keys, std::string description){
            value_ = value;
            keys_ = keys;
            description_ = description;
        }

        T getValue(){
            return value_;
        }

        void setValue(T value) {
            value_ = value;
        }

        bool ifOptionMatch(std::string option){
            for (std::string key : keys_){
                if (option == key){
                    return true;
                }
            }
            return false;
        }
    
    private:
        UserOption(){}
};

class DeviceInfo {
    private:
        // optional user input
        int number_of_devices_ = 1;

        // assume that all devices has the same values
        std::string operation_mode_ = "Came1USB1";
        bool gendc_streaming_mode_ = false;
        int width_ = 1;
        int height_ = 1;
        int payload_size_ = 1;
        std::string pixel_format_ = "RGB8";

        int num_devices_ = 1;

        GError *error = nullptr;
        
    public:
        DeviceInfo(int user_input_num_device = 1){
            arv_update_device_list ();
            int num_connected_device = static_cast<int>(arv_get_n_devices ());
            if (num_connected_device < 1){
                throw std::runtime_error("Device is not connected.");
            }

            const char* dev_id = arv_get_device_id (0);
            ArvDevice* device = arv_open_device(dev_id, nullptr);

            // determine the number of device to test 
            num_devices_ = user_input_num_device;
            if (arv_device_is_feature_available(device, "OperationMode", &error)){
                operation_mode_ = std::string(arv_device_get_string_feature_value(device, "OperationMode", &error));
                std::cout << operation_mode_ << std::endl;

                int expected_number_of_devices 
                    = operation_mode_ == "Came1USB1" ? 1
                    : operation_mode_ == "Came1USB2" ? 1
                    : operation_mode_ == "Came2USB2" ? 2
                    : operation_mode_ == "Came2USB2" ? 2 : 0;
                if (expected_number_of_devices != user_input_num_device){
                    logWarning("While OperationMode is set to " + operation_mode_ + ", the number of device is set to " + std::to_string(user_input_num_device));   
                }
                num_devices_ = expected_number_of_devices;
            }
            if (num_connected_device < num_devices_){
                g_object_unref (device);
                throw std::runtime_error("The user input -nd/--number-of-device is invalid.");
            }

            if (arv_device_is_feature_available(device, "GenDCDescriptor", &error)
                && arv_device_is_feature_available(device, "GenDCStreamingMode", &error)
                && arv_device_get_string_feature_value(device, "GenDCStreamingMode", &error) == "On"
            ){
                gendc_streaming_mode_ = true;
            }

            width_ = static_cast<int>(arv_device_get_integer_feature_value(device, "Width", &error));
            height_ = static_cast<int>(arv_device_get_integer_feature_value(device, "Height", &error));
            payload_size_ = static_cast<int>(arv_device_get_integer_feature_value(device, "PayloadSize", &error));
            pixel_format_ = arv_device_get_string_feature_value(device, "PixelFormat", &error);

            g_object_unref (device);

            displayInfo();
        }

        std::string getPixelFormat(){
            return pixel_format_;
        }

        bool isGenDCMode(){
            return gendc_streaming_mode_;
        }

        int getNumDevice(){
            return num_devices_;
        }

        int getWidth(){
            return width_;
        }

        int getHeight(){
            return height_;
        }

        int getPayloadSize(){
            return payload_size_;
        }

    private:
        DeviceInfo(){}

        void displayInfo(){
            logInfo("OperationMode: ", operation_mode_);
            logInfo("Number of devices: ", num_devices_);
            logInfo("GenDCStreamingMode: ", gendc_streaming_mode_ ? "true" : "false");
            logInfo("Width: ", width_);
            logInfo("Height: ", height_);
            logInfo("PayloadSize: ", payload_size_);
            logInfo("PixelFormat: ", pixel_format_);
        }
};

class TestInfo {
    private:
        // optional user input
        std::string directory_;
        int number_of_frames_;
        int number_of_tests_;

        bool realtime_display_mode_;
        bool realtime_evaluation_mode_;
        bool delete_bins_;
        
    public:
        TestInfo(std::string directory, int num_frame, int num_test,
            bool realtime_display, bool realtime_evaluation, bool delete_bin
        ): directory_(directory), number_of_frames_(num_frame), number_of_tests_(num_test),
            realtime_display_mode_(realtime_display), realtime_evaluation_mode_(realtime_evaluation),
            delete_bins_(delete_bin)
        {
            displayInfo();
        }

    bool isRealtimeDisplayMode(){
        return realtime_display_mode_;
    }

    bool isRealtimeEvaluationMode(){
        return realtime_evaluation_mode_;
    }

    int getNumFrames(){
        return number_of_frames_;
    }

    private:
        TestInfo(){}

        void displayInfo(){
            logInfo("Saving Directory: ", directory_);
            logInfo("Number of frames: ", number_of_frames_);
            logInfo("Number of tests: ", number_of_tests_);
            logInfo("Realtime display mode: ", realtime_display_mode_ ? "true" : "false");
            logInfo("Realtime evaluation mode: ", realtime_evaluation_mode_ ? "true" : "false");
            logInfo("Delete bin files: ", delete_bins_ ? "true" : "false");
        }  
};

std::string getImageAcquisitionBB(bool gendc, std::string pixel_format){
    if (gendc){
        return "image_io_u3v_gendc";
    }

    if (pixel_format == "Mono8"){
        return "image_io_u3v_cameraN_u8x2";
    } else if (pixel_format == "Mono10" || pixel_format == "Mono12"){
        return "image_io_u3v_cameraN_u16x2";
    } else if (pixel_format == "RGB8" || pixel_format == "BGR8"){
        return "image_io_u3v_cameraN_u8x3";
    } else{
        throw std::runtime_error( pixel_format + " is currently not supported.");
    }
}

void getFrameCountFromBin(std::string output_directory, std::map<int, std::vector<int>>& framecount_record){
    logStatus("Post recording Process... Framecount data is generated.");

}

template<typename U>
void process_and_save(DeviceInfo& device_info, TestInfo& test_info, std::string output_directory_path_,
    std::map<int, std::vector<int>>& framecount_record){
    // pipeline setup
    ion::Builder b;
    b.set_target(ion::get_host_target());
    b.with_bb_module("ion-bb");

    // the first BB: Obtain GenDC/images
    ion::Node n = b.add(getImageAcquisitionBB(device_info.isGenDCMode(), device_info.getPixelFormat()))()
      .set_param(
        ion::Param("num_devices", device_info.getNumDevice()),
        ion::Param("frame_sync", true),
        ion::Param("realtime_diaplay_mode", test_info.isRealtimeDisplayMode())
      );

    // the second BB: optional
    if (test_info.isRealtimeEvaluationMode()){
        logStatus("Recording and evaluating Process... Framecount is stored during the record.");


        std::vector< int > buf_size = std::vector < int >{ device_info.getWidth(), device_info.getHeight() };
        if (device_info.getPixelFormat() == "RGB8"){
            buf_size.push_back(3);
        }
        std::vector<Halide::Buffer<U>> output;
        for (int i = 0; i < device_info.getNumDevice(); ++i){
        output.push_back(Halide::Buffer<U>(buf_size));
        }
        n["output"].bind(output);

        Halide::Buffer<uint32_t> frame_counts = Halide::Buffer<uint32_t>(device_info.getNumDevice());
        n["frame_count"].bind(frame_counts);

        for (int x = 0; x < test_info.getNumFrames(); ++x){
            b.run();
            for (int d = 0; d < device_info.getNumDevice(); ++d){
                framecount_record[d].push_back(frame_counts(d));
            }
        }
        return;
    }else{
        logStatus("Recording Process... Bin files are generated.");

        if (device_info.isGenDCMode()){
            int payloadsize = device_info.getPayloadSize();
            n = b.add("image_io_binary_gendc_saver")(n["gendc"], n["device_info"], &payloadsize)
                .set_param(
                    ion::Param("num_devices", device_info.getNumDevice()),
                    ion::Param("output_directory", output_directory_path_),
                    ion::Param("input_gendc.size", device_info.getNumDevice()),
                    ion::Param("input_deviceinfo.size", device_info.getNumDevice())
                );
        }else{
            std::string bb_save_image = device_info.getPixelFormat() == "Mono8" ? "image_io_binarysaver_u8x2" 
                : "Mono10" || "Mono12"  ? "image_io_binarysaver_u16x2" : "image_io_binarysaver_u8x3";
            int width = device_info.getWidth();
            int height = device_info.getHeight();
            n = b.add(bb_save_image)(n["output"], n["device_info"], n["frame_count"], &width, &height)
                .set_param(
                    ion::Param("output_directory", output_directory_path_),
                    ion::Param("input_images.size", device_info.getNumDevice()),
                    ion::Param("input_deviceinfo.size", device_info.getNumDevice())
                );
        }
        Halide::Buffer<int> terminator = Halide::Buffer<int>::make_scalar();
        n["output"].bind(terminator);

        for (int x = 0; x < test_info.getNumFrames(); ++x){
            b.run();
        }
        getFrameCountFromBin(output_directory_path_, framecount_record);
    }
}




int main(int argc, char *argv[])
{
    UserOption<std::string> directory(".", std::vector<std::string>{"-d", "--directory"}, "Directory to save log");
    UserOption<int> num_device(1, std::vector<std::string>{"-nd", "--number-of-device"}, "The number of devices");
    UserOption<int> num_frame(100, std::vector<std::string>{"-nf", "--number-of-frames"}, "The number of frames to obtain per test");
    UserOption<int> num_test(2, std::vector<std::string>{"-nt", "--number-of-tests"}, "The number of tests to perform in this script");
    UserOption<bool> realtime_display(false, std::vector<std::string>{"-rt", "--realtime-display-mode"}, "Image capture in Realtime-display mode");
    UserOption<bool> realtime_evaluation(false, std::vector<std::string>{"-re", "--realtime-evaluation-mode"}, "Run performance test in Realtime-evaluation");
    UserOption<bool> delete_bin(false, std::vector<std::string>{"-db", "--delete-bins"}, "Delete bin files in --realtime-ecaluation-mode");

    if (argc > 1){
        for (int i = 1; i < argc; i++){
            std::string arg = argv[i];

            if (directory.ifOptionMatch(argv[i])){
                directory.setValue(argv[++i]);
            } else if (num_device.ifOptionMatch(argv[i])){
                num_device.setValue(std::stoi(argv[++i]));
            } else if (num_frame.ifOptionMatch(argv[i])){
                num_frame.setValue(std::stoi(argv[++i]));
            } else if (num_test.ifOptionMatch(argv[i])){
                num_test.setValue(std::stoi(argv[++i]));
            } else if (realtime_display.ifOptionMatch(argv[i])){
                realtime_display.setValue(true);
            } else if (realtime_evaluation.ifOptionMatch(argv[i])){
                realtime_evaluation.setValue(true);
            } else if (delete_bin.ifOptionMatch(argv[i])){
                delete_bin.setValue(true);
            }
        }
    }

    std::string saving_directory_prefix = "U3V-performance-test-";
    if (realtime_evaluation.getValue()){
        saving_directory_prefix += "without-saving-";
    }

    if (!std::filesystem::exists(directory.getValue())){
        std::filesystem::create_directory(directory.getValue());
    }
    std::time_t now;
    std::time(&now);
    std::tm tm;
    localtime_s(&tm, &now);
    std::stringstream ss;
    ss << saving_directory_prefix << std::put_time(&tm, "%Y-%m-%d-%H-%M-%S");
    std::filesystem::path saving_path = std::filesystem::path(directory.getValue()) / std::filesystem::path(ss.str());
    std::filesystem::create_directory(saving_path);

    DeviceInfo device_info(num_device.getValue());
    TestInfo test_info(directory.getValue(), num_frame.getValue(), num_test.getValue(),
        realtime_display.getValue(), realtime_evaluation.getValue(), delete_bin.getValue()
    );

    for (int i = 0; i < num_test.getValue(); ++i){
        std::filesystem::path ith_test_output_directory = saving_path / std::filesystem::path(std::to_string(i));
        std::filesystem::create_directory(ith_test_output_directory);

        std::map<int, std::vector<int>> framecount_record;
        for (int d = 0; d < device_info.getNumDevice(); ++d){
            framecount_record[d] = std::vector<int>();
        }
        if (device_info.getPixelFormat() == "Mono8" || device_info.getPixelFormat() == "RGB8"){
            process_and_save<uint8_t>(device_info, test_info, ith_test_output_directory.u8string(), framecount_record);
        }else{
            // std::cout << ith_test_output_directory << std::endl;
            process_and_save<uint16_t>(device_info, test_info, ith_test_output_directory.u8string(), framecount_record);
        }
        
    }

    

    return 0;
}